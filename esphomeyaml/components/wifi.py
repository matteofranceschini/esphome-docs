import voluptuous as vol

import esphomeyaml.config_validation as cv
from esphomeyaml import core
from esphomeyaml.const import CONF_AP, CONF_CHANNEL, CONF_DNS1, CONF_DNS2, CONF_DOMAIN, \
    CONF_GATEWAY, CONF_HOSTNAME, CONF_ID, CONF_MANUAL_IP, CONF_NETWORKS, CONF_PASSWORD, CONF_SSID, \
    CONF_STATIC_IP, CONF_SUBNET, ESP_PLATFORM_ESP8266
from esphomeyaml.helpers import App, Pvariable, StructInitializer, add, esphomelib_ns, global_ns


def validate_password(value):
    value = cv.string(value)
    if not value:
        return value
    if len(value) < 8:
        raise vol.Invalid(u"WPA password must be at least 8 characters long")
    if len(value) > 63:
        raise vol.Invalid(u"WPA password must be at most 63 characters long")
    return value


def validate_channel(value):
    value = cv.positive_int(value)
    if value < 1:
        raise vol.Invalid("Minimum WiFi channel is 1")
    if value > 14:
        raise vol.Invalid("Maximum WiFi channel is 14")
    return value


AP_MANUAL_IP_SCHEMA = vol.Schema({
    vol.Required(CONF_STATIC_IP): cv.ipv4,
    vol.Required(CONF_GATEWAY): cv.ipv4,
    vol.Required(CONF_SUBNET): cv.ipv4,
})

STA_MANUAL_IP_SCHEMA = AP_MANUAL_IP_SCHEMA.extend({
    vol.Inclusive(CONF_DNS1, 'dns'): cv.ipv4,
    vol.Inclusive(CONF_DNS2, 'dns'): cv.ipv4,
})

CONF_BSSID = 'bssid'

WIFI_NETWORK_BASE = vol.Schema({
    vol.Optional(CONF_SSID): cv.ssid,
    vol.Optional(CONF_PASSWORD): validate_password,
    vol.Optional(CONF_BSSID): cv.mac_address,
    vol.Optional(CONF_CHANNEL): validate_channel,
    vol.Optional(CONF_MANUAL_IP): AP_MANUAL_IP_SCHEMA,
})

WIFI_NETWORK_AP = vol.All(WIFI_NETWORK_BASE.extend({
    vol.Optional(CONF_MANUAL_IP): AP_MANUAL_IP_SCHEMA,
}), cv.has_at_least_one_key(CONF_SSID, CONF_BSSID))

WIFI_NETWORK_STA = vol.All(WIFI_NETWORK_BASE.extend({
    vol.Optional(CONF_MANUAL_IP): STA_MANUAL_IP_SCHEMA,
}), cv.has_at_least_one_key(CONF_SSID, CONF_BSSID))


def validate_multi_wifi(config):
    if CONF_PASSWORD in config and CONF_SSID not in config:
        raise vol.Invalid("Cannot have WiFi password without SSID!")
    if CONF_SSID in config and CONF_NETWORKS in config:
        raise vol.Invalid("For multi-wifi mode (with 'networks:'), please specify all "
                          "networks within the 'networks:' key!")

    return config


# pylint: disable=invalid-name
IPAddress = global_ns.IPAddress
ManualIP = esphomelib_ns.ManualIP
WiFiComponent = esphomelib_ns.WiFiComponent
WiFiAp = esphomelib_ns.WiFiAp

CONFIG_SCHEMA = vol.All(vol.Schema({
    cv.GenerateID(): cv.declare_variable_id(WiFiComponent),
    vol.Optional(CONF_SSID): cv.ssid,
    vol.Optional(CONF_PASSWORD): validate_password,
    vol.Optional(CONF_NETWORKS): vol.All(cv.ensure_list, [WIFI_NETWORK_STA]),
    vol.Optional(CONF_AP): WIFI_NETWORK_AP,
    vol.Optional(CONF_HOSTNAME): cv.hostname,
    vol.Optional(CONF_DOMAIN, default='.local'): cv.domainname,

    vol.Optional(CONF_MANUAL_IP): cv.invalid("Manual IPs can only be specified in the 'networks:' "
                                             "section of the WiFi configuration since 1.7.0"),
}), validate_multi_wifi)


def safe_ip(ip):
    if ip is None:
        return IPAddress(0, 0, 0, 0)
    return IPAddress(*ip.args)


def manual_ip(config):
    if config is None:
        return None
    return StructInitializer(
        ManualIP,
        ('static_ip', safe_ip(config[CONF_STATIC_IP])),
        ('gateway', safe_ip(config[CONF_GATEWAY])),
        ('subnet', safe_ip(config[CONF_SUBNET])),
        ('dns1', safe_ip(config.get(CONF_DNS1))),
        ('dns2', safe_ip(config.get(CONF_DNS2))),
    )


def wifi_network(config):
    return StructInitializer(
        WiFiAp,
        ('ssid', config.get(CONF_SSID, "")),
        ('password', config.get(CONF_PASSWORD, "")),
        ('bssid', config.get(CONF_BSSID, core.MACAddress(0, 0, 0, 0, 0, 0)).as_hex()),
        ('channel', config.get(CONF_CHANNEL, -1)),
        ('manual_ip', manual_ip(config.get(CONF_MANUAL_IP))),
    )


def to_code(config):
    if CONF_SSID in config:
        rhs = App.init_wifi(config[CONF_SSID], config.get(CONF_PASSWORD))
    else:
        rhs = App.init_wifi()
    wifi = Pvariable(config[CONF_ID], rhs)

    for network in config.get(CONF_NETWORKS, []):
        add(wifi.add_sta(wifi_network(network)))

    if CONF_AP in config:
        add(wifi.set_ap(wifi_network(config[CONF_AP])))

    if CONF_HOSTNAME in config:
        add(wifi.set_hostname(config[CONF_HOSTNAME]))


def lib_deps(config):
    if core.ESP_PLATFORM == ESP_PLATFORM_ESP8266:
        return 'ESP8266WiFi'
    return None