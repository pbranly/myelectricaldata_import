"""Export data to Home Assistant with robust error handling."""

import json
import logging
from datetime import datetime, timedelta

import pytz
from dateutil.relativedelta import relativedelta

from dependencies import get_version, truncate
from init import CONFIG, DB, MQTT
from models.stat import Stat

UTC = pytz.UTC


def convert_kw(value):
    return truncate(value / 1000, 2)


def convert_kw_to_euro(value, price):
    if isinstance(price, str):
        price = float(price.replace(",", "."))
    return round(value / 1000 * price, 1)


def convert_price(price):
    if isinstance(price, str):
        price = price.replace(",", ".")
    return float(price)


class HomeAssistant:
    class Config:
        def __init__(self):
            self.consumption: bool = True
            self.consumption_detail: bool = True
            self.production: bool = False
            self.production_detail: bool = False
            self.consumption_price_base: float = 0
            self.consumption_price_hp: float = 0
            self.consumption_price_hc: float = 0
            self.production_price: float = 0
            self.discovery_prefix: str = "home_assistant"
            self.activation_date: datetime = None
            self.subscribed_power: str = None
            self.consumption_max_power: bool = True
            self.offpeak_hours_0: str = None
            self.offpeak_hours_1: str = None
            self.offpeak_hours_2: str = None
            self.offpeak_hours_3: str = None
            self.offpeak_hours_4: str = None
            self.offpeak_hours_5: str = None
            self.offpeak_hours_6: str = None

    def __init__(self, usage_point_id):
        self.usage_point_id = usage_point_id
        self.date_format = "%Y-%m-%d"
        self.date_format_detail = "%Y-%m-%d %H:%M:%S"
        self.config_usage_point = DB.get_usage_point(self.usage_point_id)
        self.config = None
        self.load_config()
        self.usage_point = DB.get_usage_point(self.usage_point_id)
        self.mqtt = MQTT
        self.tempo_color = None

    def load_config(self):
        self.config = self.Config()
        for key in self.config.__dict__:
            if hasattr(self.config_usage_point, key):
                setattr(self.config, key, getattr(self.config_usage_point, key))
        config_ha_config = CONFIG.home_assistant_config()
        for key in self.config.__dict__:
            if key in config_ha_config:
                setattr(self.config, key, config_ha_config[key])
        contract = DB.get_contract(self.usage_point_id)
        for key in self.config.__dict__:
            if hasattr(contract, key):
                setattr(self.config, key, getattr(contract, key))

    def sensor(self, **kwargs):
        topic = f"{self.config.discovery_prefix}/sensor/{kwargs['topic']}"
        config = {
            "name": kwargs["name"],
            "uniq_id": kwargs["uniq_id"],
            "stat_t": f"{topic}/state",
            "json_attr_t": f"{topic}/attributes",
            "device_class": kwargs.get("device_class"),
            "device": {
                "identifiers": kwargs["device_identifiers"],
                "name": kwargs["device_name"],
                "model": kwargs["device_model"],
                "manufacturer": "MyElectricalData",
            },
        }
        if "unit_of_measurement" in kwargs:
            config["unit_of_measurement"] = kwargs["unit_of_measurement"]
        attributes = {
            **kwargs.get("attributes", {}),
            "version": get_version(),
            "activationDate": self.config.activation_date,
            "lastUpdate": datetime.now(tz=UTC).strftime(self.date_format_detail),
            "timeLastCall": datetime.now(tz=UTC).strftime(self.date_format_detail),
        }
        data = {
            "config": json.dumps(config),
            "state": kwargs["state"],
            "attributes": json.dumps(attributes),
        }
        return self.mqtt.publish_multiple(data, topic)

    def last_x_day(self, days, measurement_direction):
        uniq_id = f"myelectricaldata_linky_{self.usage_point_id}_{measurement_direction}_last{days}day"
        end = datetime.combine(datetime.now(tz=UTC) - timedelta(days=1), datetime.max.time())
        begin = datetime.combine(end - timedelta(days), datetime.min.time())
        range_data = DB.get_detail_range(self.usage_point_id, begin, end, measurement_direction) or []
        attributes = {"time": [], measurement_direction: []}
        for data in range_data:
            attributes["time"].append(data.date.strftime("%Y-%m-%d %H:%M:%S"))
            attributes[measurement_direction].append(data.value)
        self.sensor(
            topic=f"myelectricaldata_{measurement_direction}_last_{days}_day/{self.usage_point_id}",
            name=f"{measurement_direction}.last{days}day",
            device_name=f"Linky {self.usage_point_id}",
            device_model=f"linky {self.usage_point_id}",
            device_identifiers=f"{self.usage_point_id}",
            uniq_id=uniq_id,
            unit_of_measurement="kWh",
            attributes=attributes,
            state=days,
            device_class="energy",
            numPDL=self.usage_point_id,
        )

    def history_usage_point_id(self, measurement_direction):
        uniq_id = f"myelectricaldata_linky_{self.usage_point_id}_{measurement_direction}_history"
        stats = Stat(self.usage_point_id, measurement_direction)
        state_obj = DB.get_daily_last(self.usage_point_id, measurement_direction)
        state = convert_kw(state_obj.value) if state_obj else 0
        attributes = {"yesterdayDate": getattr(stats.daily(0), "begin", "")}
        self.sensor(
            topic=f"myelectricaldata_{measurement_direction}_history/{self.usage_point_id}",
            name=f"{measurement_direction}.history",
            device_name=f"Linky {self.usage_point_id}",
            device_model=f"linky {self.usage_point_id}",
            device_identifiers=f"{self.usage_point_id}",
            uniq_id=uniq_id,
            unit_of_measurement="kWh",
            attributes=attributes,
            state=state,
            device_class="energy",
            numPDL=self.usage_point_id,
        )

    def myelectricaldata_usage_point_id(self, measurement_direction):
        stats = Stat(self.usage_point_id, measurement_direction)
        state_obj = DB.get_daily_last(self.usage_point_id, measurement_direction)
        state = state_obj.value if state_obj else 0

        # Sécurisation de l'accès aux listes Tempo
        dailyweek_hp, dailyweek_hc = [], []
        for i in range(7):
            try:
                tempo_data = stats.tempo(i).get("value", {})
            except (IndexError, AttributeError):
                tempo_data = {"blue_hp": 0, "white_hp": 0, "red_hp": 0, "blue_hc": 0, "white_hc": 0, "red_hc": 0}
            hp = tempo_data.get("blue_hp", 0) + tempo_data.get("white_hp", 0) + tempo_data.get("red_hp", 0)
            hc = tempo_data.get("blue_hc", 0) + tempo_data.get("white_hc", 0) + tempo_data.get("red_hc", 0)
            dailyweek_hp.append(convert_kw(hp))
            dailyweek_hc.append(convert_kw(hc))

        state_to_publish = convert_kw(state)
        uniq_id = f"myelectricaldata_linky_{self.usage_point_id}_{measurement_direction}"
        self.sensor(
            topic=f"myelectricaldata_{measurement_direction}/{self.usage_point_id}",
            name=f"{measurement_direction}",
            device_name=f"Linky {self.usage_point_id}",
            device_model=f"linky {self.usage_point_id}",
            device_identifiers=f"{self.usage_point_id}",
            uniq_id=uniq_id,
            state=state_to_publish,
            device_class="energy",
            numPDL=self.usage_point_id,
        )

    def tempo(self):
        for delta, name in [(0, "today"), (1, "tomorrow")]:
            begin = datetime.combine(datetime.now(tz=UTC) + timedelta(days=delta), datetime.min.time())
            end = datetime.combine(datetime.now(tz=UTC) + timedelta(days=delta), datetime.max.time())
            tempo_data = DB.get_tempo_range(begin, end, "asc") or []
            if tempo_data:
                date = tempo_data[0].date.strftime(self.date_format_detail)
                state = getattr(tempo_data[0], "color", "Inconnu")
            else:
                date = begin.strftime(self.date_format_detail)
                state = "Inconnu"
            self.tempo_color = state if delta == 0 else self.tempo_color
            self.sensor(
                topic=f"myelectricaldata_rte/tempo_{name}",
                name=name.capitalize(),
                device_name="RTE Tempo",
                device_model="RTE",
                device_identifiers="rte_tempo",
                uniq_id=f"myelectricaldata_tempo_{name}",
                attributes={"date": date},
                state=state,
            )

    def tempo_days(self):
        tempo_days = DB.get_tempo_config("days") or {}
        for color, days in tempo_days.items():
            self.tempo_days_sensor(color, days)

    def tempo_days_sensor(self, color, days):
        self.sensor(
            topic=f"myelectricaldata_edf/tempo_days_{color}",
            name=f"Days {color.capitalize()}",
            device_name="EDF Tempo",
            device_model="EDF",
            device_identifiers="edf_tempo",
            uniq_id=f"myelectricaldata_tempo_days_{color}",
            state=days,
        )

    def tempo_price(self):
        tempo_price = DB.get_tempo_config("price") or {}
        for color, price in tempo_price.items():
            self.tempo_price_sensor(
                color,
                float(price.replace(",", ".")) if isinstance(price, str) else price,
                f"{color.split('_')[0].capitalize()}{color.split('_')[1].capitalize()}",
            )

    def tempo_price_sensor(self, color, price, name):
        self.sensor(
            topic=f"myelectricaldata_edf/tempo_price_{color}",
            name=f"Price {name[:-2]} {name[-2:]}",
            device_name="EDF Tempo",
            device_model="EDF",
            device_identifiers="edf_tempo",
            uniq_id=f"myelectricaldata_tempo_price_{color}",
            state=convert_price(price),
            unit_of_measurement="EUR/kWh",
        )

    def ecowatt(self):
        for delta, name in [(0, "J0"), (1, "J1"), (2, "J2")]:
            self.ecowatt_delta(name, delta)

    def ecowatt_delta(self, name, delta):
        current_date = datetime.combine(datetime.now(tz=UTC) + timedelta(days=delta), datetime.min.time())
        fetch_date = current_date - timedelta(days=1)
        ecowatt_data = DB.get_ecowatt_range(fetch_date, fetch_date, "asc") or []
        day_value = 0
        forecast = {}
        for data in ecowatt_data:
            day_value = getattr(data, "value", 0)
            details = getattr(data, "detail", "{}")
            for date_str, value in json.loads(details.replace("'", '"')).items():
                try:
                    date = datetime.strptime(date_str, self.date_format_detail)
                    forecast[f'{date.strftime("%H")} h'] = value
                except Exception:
                    continue
        self.sensor(
            topic=f"myelectricaldata_rte/ecowatt_{name}",
            name=name,
            device_name="RTE EcoWatt",
            device_model="RTE",
            device_identifiers="rte_ecowatt",
            uniq_id=f"myelectricaldata_ecowatt_{name}",
            attributes={"date": current_date.strftime(self.date_format), "forecast": forecast},
            state=day_value,
        )
