/*
 * Copyright (c) 2022 Nordic Semiconductor ASA
 *
 * SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
 */

/**
 * @file
 *   This file implements the nRF700x Coexistence interface.
 *
 */

#if !defined(CONFIG_MPSL_CX_PIN_FORWARDER)
#include <mpsl_cx_abstract_interface.h>
#include <mpsl/mpsl_cx_nrf700x.h>
#else
#include <string.h>
#include <soc_secure.h>
#endif

#include <stddef.h>
#include <stdint.h>

#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/devicetree.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/atomic.h>
#include <soc_nrf_common.h>

#include "hal/nrf_gpio.h"
#include <nrfx_gpiote.h>
#include <gpiote_nrfx.h>

#include <zephyr/logging/log.h>
LOG_MODULE_REGISTER(mpsl_cx_nrf700x, CONFIG_MPSL_CX_LOG_LEVEL);

/*
 * Typical part of device tree describing coex (sample port and pin numbers).
 *
 * / {
 *     nrf_radio_coex: nrf7002-coex {
 *         status = "okay";
 *         compatible = "nordic,nrf700x-coex";
 *         req-gpios =     <&gpio0 24 (GPIO_ACTIVE_HIGH)>;
 *         status0-gpios = <&gpio0 14 (GPIO_ACTIVE_HIGH)>;
 *         grant-gpios =   <&gpio0 25 (GPIO_ACTIVE_HIGH | GPIO_PULL_UP)>;
 *     };
 * };
 *
 */

#if DT_NODE_EXISTS(DT_NODELABEL(nrf_radio_coex))
#define CX_NODE DT_NODELABEL(nrf_radio_coex)
#else
#define CX_NODE DT_INVALID_NODE
#error No enabled coex nodes registered in DTS.
#endif

#if !defined(CONFIG_MPSL_CX_PIN_FORWARDER)

#define REQUEST_LEAD_TIME 0U

#define REQ_PIN_PORT_NO     DT_PROP(DT_GPIO_CTLR(CX_NODE, req_gpios), port)
#define STATUS0_PIN_PORT_NO DT_PROP(DT_GPIO_CTLR(CX_NODE, status0_gpios), port)
#define GRANT_PIN_PORT_NO   DT_PROP(DT_GPIO_CTLR(CX_NODE, grant_gpios), port)
#define GRANT_PIN_PIN_NO    DT_GPIO_PIN(CX_NODE, grant_gpios)

#define DELAY_LOG_SIZE        500
#define DELAY_PRINT_TIMER_SEC 45

#if defined(CONFIG_SOC_NRF54H20_CPURAD)
#if (REQ_PIN_PORT_NO == 6) || (REQ_PIN_PORT_NO == 7) || (STATUS0_PIN_PORT_NO == 6) ||              \
	(STATUS0_PIN_PORT_NO == 7) || (GRANT_PIN_PORT_NO == 6) || (GRANT_PIN_PORT_NO == 7)
#error "GPIO ports 6 and 7 cannot be used for coexistence pins"
#endif
#endif

static nrfx_gpiote_t *gpiote =
	&GPIOTE_NRFX_INST_BY_NODE(NRF_DT_GPIOTE_NODE(CX_NODE, grant_gpios));

static const struct gpio_dt_spec req_spec     = GPIO_DT_SPEC_GET(CX_NODE, req_gpios);
static const struct gpio_dt_spec status0_spec = GPIO_DT_SPEC_GET(CX_NODE, status0_gpios);
static const struct gpio_dt_spec grant_spec   = GPIO_DT_SPEC_GET(CX_NODE, grant_gpios);

#if !defined(CONFIG_SOC_SERIES_BSIM_NRFXX)
/* Direct register access pointers for ISR-safe GPIO control from DT */
static NRF_GPIO_Type *req_port =
	((NRF_GPIO_Type *)DT_REG_ADDR(DT_GPIO_CTLR(CX_NODE, req_gpios)));
static NRF_GPIO_Type *status0_port =
	((NRF_GPIO_Type *)DT_REG_ADDR(DT_GPIO_CTLR(CX_NODE, status0_gpios)));
static NRF_GPIO_Type *grant_port =
	((NRF_GPIO_Type *)DT_REG_ADDR(DT_GPIO_CTLR(CX_NODE, grant_gpios)));
static uint32_t req_pin_mask = BIT(DT_GPIO_PIN(CX_NODE, req_gpios));
static uint32_t status0_pin_mask = BIT(DT_GPIO_PIN(CX_NODE, status0_gpios));
static uint32_t grant_pin_mask = BIT(DT_GPIO_PIN(CX_NODE, grant_gpios));
#endif

static mpsl_cx_cb_t callback;
static struct gpio_callback grant_cb;
static uint32_t grant_abs_pin;

static bool enabled = true;

/* logging connection delay timings */
static uint32_t start_time;
/* need to track first request call */
static atomic_t already_requesting;
/* these must be atomic, see grant_pin_is_asserted() */
static atomic_t num_small_delays;
static atomic_t delay_i;
static uint32_t delays[DELAY_LOG_SIZE]; /* in ms */

/* NOTE that this func can have multiple threads in it at the same time, spec only guarantees
non-self-preemting calls for external funcs but this func can be called by granted_ops_get() and
gpiote_irq_handler() as an internal func */
static int32_t grant_pin_is_asserted(bool *is_asserted)
{
#if defined(CONFIG_SOC_SERIES_BSIM_NRFXX)
	int ret;

	ret = gpio_pin_get_dt(&grant_spec);

	if (ret < 0) {
		return ret;
	}

	*is_asserted = (bool)ret;
#else
	uint32_t port_in = nrf_gpio_port_in_read(grant_port);
	bool raw_value = (bool)(port_in & grant_pin_mask);

	*is_asserted = (grant_spec.dt_flags & GPIO_ACTIVE_LOW) ? !raw_value : raw_value;
#endif

	/* measures delay between request and grant pin being active, checking if we're currently
	requesting. already set is_asserted by now so we can reset already_requesting */
	if (*is_asserted) {
		uint32_t local_start_time = start_time; /* stored since test and set may re-write start_time */
		if (atomic_cas(&already_requesting, 1, 0)) {
			uint32_t delta = (uint32_t) k_cyc_to_ms_floor32(k_cycle_get_32() - local_start_time);
			if (delta < 10) {
				atomic_inc(&num_small_delays);
			}
			else {
				atomic_val_t current_index = atomic_inc(&delay_i); /* atomic fetch and add */
				if (current_index < DELAY_LOG_SIZE) { /* set before compare to avoid race condition */
					delays[current_index] = delta;
				}
			}
		}
	}
	return 0;
}

void mpsl_cx_nrf700x_print_delay_log(void)
{
	atomic_val_t delay_index = atomic_get(&delay_i);

	LOG_INF("[nick's logging] number of delays below 10 ms: %ld", atomic_get(&num_small_delays));
	LOG_INF("[nick's logging] number of delays above 10 ms: %ld (%u log size)",
			delay_index, DELAY_LOG_SIZE);
	LOG_RAW("[nick's logging] specific delays above 10 ms: ");
	for (int i = 0; i < (delay_index > DELAY_LOG_SIZE ? DELAY_LOG_SIZE : delay_index); i++) {
		LOG_RAW("%u ", delays[i]);
	}
	LOG_RAW("\n");
}

/* started in mpsl_cx_init, runs after DELAY_PRINT_TIMER_SEC */
static void stats_log_timer_expiry(struct k_timer *timer)
{
	mpsl_cx_nrf700x_print_delay_log();
}
K_TIMER_DEFINE(stats_log_timer, stats_log_timer_expiry, NULL);

static mpsl_cx_op_map_t granted_ops_map(bool grant_is_asserted)
{
	mpsl_cx_op_map_t granted_ops = MPSL_CX_OP_IDLE_LISTEN | MPSL_CX_OP_RX;

	if (grant_is_asserted || !enabled) {
		granted_ops |= MPSL_CX_OP_TX;
	}

	return granted_ops;
}

static int32_t granted_ops_get(mpsl_cx_op_map_t *granted_ops)
{
	int  ret;
	bool grant_is_asserted;

	ret = grant_pin_is_asserted(&grant_is_asserted);
	if (ret < 0) {
		return ret;
	}

	*granted_ops = granted_ops_map(grant_is_asserted);
	return 0;
}

static void gpiote_irq_handler(const struct device *gpiob, struct gpio_callback *cb, uint32_t pins)
{
	(void)gpiob;
	(void)cb;
	(void)pins;

	static mpsl_cx_op_map_t last_notified;
	int32_t ret;
	mpsl_cx_op_map_t granted_ops;
	mpsl_cx_cb_t callback_copy = callback;

	if (callback_copy != NULL) {
		ret = granted_ops_get(&granted_ops);

		__ASSERT(ret == 0, "Getting grant pin state returned unexpected result: %d", ret);
		if (ret != 0) {
			/* nrfx gpio implementation cannot return failure for this call
			 * This condition is handled for fail-safe approach. It is assumed
			 * GRANT is not given, if cannot read its value
			 */
			granted_ops = granted_ops_map(false);
		}

		if (granted_ops != last_notified) {
			last_notified = granted_ops;
			callback_copy(granted_ops);
		}
	}
}

/**
 * Calculates logic level of @c dir signal depending on operation
 *
 * @param   ops     Operations requested
 * @retval  0       @c dir signal should be inactive
 * @retval  other   @c dir signal should be active
 */
static int sig_dir_level_calc(mpsl_cx_op_map_t ops)
{
	int r = 1;

	if (ops & MPSL_CX_OP_TX) {
		r = 0;
	}

	return r;
}

/**
 * Drives @c pri-dir pin to value of @c dir signal according to requested operation.
 *
 * @param   ops Operations requested
 * @return      Result of gpio control
 */
static int32_t gpio_drive_status0_to_dir(mpsl_cx_op_map_t ops)
{
#if defined(CONFIG_SOC_SERIES_BSIM_NRFXX)
	return gpio_pin_set_dt(&status0_spec, sig_dir_level_calc(ops));
#else
	int level = sig_dir_level_calc(ops);
	bool status0_level = (status0_spec.dt_flags & GPIO_ACTIVE_LOW) ? !level : (bool)level;

#if NRF_GPIO_HAS_RETENTION_SETCLEAR
	nrf_gpio_port_retain_disable(status0_port, status0_pin_mask);
#endif
	if (status0_level) {
		nrf_gpio_port_out_set(status0_port, status0_pin_mask);
	} else {
		nrf_gpio_port_out_clear(status0_port, status0_pin_mask);
	}
#if NRF_GPIO_HAS_RETENTION_SETCLEAR
	nrf_gpio_port_retain_enable(status0_port, status0_pin_mask);
#endif

	return 0;
#endif
}

/**
 * Drives @c req pin to value according to @p active
 *
 * @param   active   0 drives to inactive level. Non-zero drives to active level
 * @return           Result of gpio control
 */
static int32_t gpio_drive_request(int active)
{
#if defined(CONFIG_SOC_SERIES_BSIM_NRFXX)
	return gpio_pin_set_dt(&req_spec, active);
#else
	bool req_level = (req_spec.dt_flags & GPIO_ACTIVE_LOW) ? !active : (bool)active;

#if NRF_GPIO_HAS_RETENTION_SETCLEAR
	nrf_gpio_port_retain_disable(req_port, req_pin_mask);
#endif
	if (req_level) {
		nrf_gpio_port_out_set(req_port, req_pin_mask);
	} else {
		nrf_gpio_port_out_clear(req_port, req_pin_mask);
	}
#if NRF_GPIO_HAS_RETENTION_SETCLEAR
	nrf_gpio_port_retain_enable(req_port, req_pin_mask);
#endif

	return 0;
#endif
}

static int32_t request(const mpsl_cx_request_t *req_params)
{
	int ret;

	/* atomically test and set first request() call; request() is called every connection interval,
	storing first request() to find time between first call and grant HIGH */
	if (atomic_cas(&already_requesting, 0, 1)) {
		start_time = k_cycle_get_32();
	}

	if (req_params == NULL) {
		return -NRF_EINVAL;
	}

	ret = gpio_drive_status0_to_dir(req_params->ops);

	if (ret < 0) {
		return -NRF_EPERM;
	}

	ret = gpio_drive_request(req_params->ops & (MPSL_CX_OP_RX | MPSL_CX_OP_TX));

	if (ret < 0) {
		return -NRF_EPERM;
	}

	return 0;
}

static int32_t release(void)
{
	int ret;

	ret = gpio_drive_request(0);
	if (ret < 0) {
		return -NRF_EPERM;
	}

	ret = gpio_drive_status0_to_dir(0);

	if (ret < 0) {
		return -NRF_EPERM;
	}

	return 0;
}

static uint32_t req_grant_delay_get(void)
{
	return REQUEST_LEAD_TIME;
}

static int32_t register_callback(mpsl_cx_cb_t cb)
{
	callback = cb;

	if (cb != NULL) {
		nrfx_gpiote_trigger_enable(gpiote, grant_abs_pin, true);
	} else {
		nrfx_gpiote_trigger_disable(gpiote, grant_abs_pin);
	}

	return 0;
}

static const mpsl_cx_interface_t m_mpsl_cx_methods = {
	.p_request             = request,
	.p_release             = release,
	.p_granted_ops_get     = granted_ops_get,
	.p_req_grant_delay_get = req_grant_delay_get,
	.p_register_callback   = register_callback,
};

static int mpsl_cx_init(void)
{
	int32_t ret;

	callback = NULL;

	ret = mpsl_cx_interface_set(&m_mpsl_cx_methods);
	if (ret != 0) {
		return ret;
	}

	ret = gpio_pin_configure_dt(&req_spec, GPIO_OUTPUT_INACTIVE);
	if (ret != 0) {
		return ret;
	}

	ret = gpio_pin_configure_dt(&status0_spec, GPIO_OUTPUT_INACTIVE);
	if (ret != 0) {
		return ret;
	}

	ret = gpio_pin_configure_dt(&grant_spec, GPIO_INPUT);
	if (ret != 0) {
		return ret;
	}

#if !defined(CONFIG_SOC_SERIES_BSIM_NRFXX)
	if (grant_port == NULL || req_port == NULL || status0_port == NULL) {
		return -EINVAL;
	}
#endif

	ret = gpio_pin_interrupt_configure_dt(&grant_spec,
			GPIO_INT_ENABLE | GPIO_INT_EDGE | GPIO_INT_EDGE_BOTH);
	if (ret < 0) {
		return ret;
	}
	grant_abs_pin = NRF_GPIO_PIN_MAP(GRANT_PIN_PORT_NO, GRANT_PIN_PIN_NO);
	nrfx_gpiote_trigger_disable(gpiote, grant_abs_pin);

	gpio_init_callback(&grant_cb, gpiote_irq_handler, BIT(grant_spec.pin));
	gpio_add_callback(grant_spec.port, &grant_cb);

	ret = gpio_drive_request(0);
	if (ret != 0) {
		return ret;
	}

	ret = gpio_drive_status0_to_dir(0);
	if (ret != 0) {
		return ret;
	}

	/* starts delay print timer */
	k_timer_start(&stats_log_timer, K_SECONDS(DELAY_PRINT_TIMER_SEC), K_NO_WAIT);

	return 0;
}

SYS_INIT(mpsl_cx_init, POST_KERNEL, CONFIG_MPSL_CX_INIT_PRIORITY);

void mpsl_cx_nrf700x_set_enabled(bool enable)
{
	enabled = enable;
}

#else // !defined(CONFIG_MPSL_CX_PIN_FORWARDER)
static int mpsl_cx_init(void)
{
#if DT_NODE_HAS_PROP(CX_NODE, req_gpios)
	uint8_t req_pin = NRF_DT_GPIOS_TO_PSEL(CX_NODE, req_gpios);

	soc_secure_gpio_pin_mcu_select(req_pin, NRF_GPIO_PIN_SEL_NETWORK);
#endif
#if DT_NODE_HAS_PROP(CX_NODE, status0_gpios)
	uint8_t status0_pin = NRF_DT_GPIOS_TO_PSEL(CX_NODE, status0_gpios);

	soc_secure_gpio_pin_mcu_select(status0_pin, NRF_GPIO_PIN_SEL_NETWORK);
#endif
#if DT_NODE_HAS_PROP(CX_NODE, grant_gpios)
	uint8_t grant_pin = NRF_DT_GPIOS_TO_PSEL(CX_NODE, grant_gpios);

	soc_secure_gpio_pin_mcu_select(grant_pin, NRF_GPIO_PIN_SEL_NETWORK);
#endif

	return 0;
}

SYS_INIT(mpsl_cx_init, PRE_KERNEL_1, CONFIG_KERNEL_INIT_PRIORITY_DEFAULT);

#endif // !defined(CONFIG_MPSL_CX_PIN_FORWARDER)
