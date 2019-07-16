#--depends-on commands
#--depends-on location
#--require-config openweathermap-api-key

from src import ModuleManager, utils

URL_WEATHER = "http://api.openweathermap.org/data/2.5/weather"

class Module(ModuleManager.BaseModule):
    def _user_location(self, user):
        user_location = user.get_setting("location", None)
        if not user_location == None:
            name = user_location.get("name", None)
            return [user_location["lat"], user_location["lon"], name]

    @utils.hook("received.command.w", alias_of="weather")
    @utils.hook("received.command.weather")
    def weather(self, event):
        """
        :help: Ottieni informazioni Meteo per una località
        :usage: [nickname]
        :require_setting: location
        :require_setting_unless: 1
        """
        api_key = self.bot.config["openweathermap-api-key"]

        location = None
        nickname = None
        if event["args"]:
            if len(event["args_split"]) == 1 and event["server"].has_user_id(
                    event["args_split"][0]):
                target_user = event["server"].get_user(event["args_split"][0])
                location = self._user_location(target_user)
                if location == None:
                    raise utils.EventError("%s doesn't have a location set"
                        % target_user.nickname)
                else:
                    nickname = target_user.nickname
        else:
            location = self._user_location(event["user"])
            nickname = event["user"].nickname
            if location == None:
                raise utils.EventError("Non hai una località impostata")

        args = {"units": "metric", "APPID": api_key}

        location_name = None
        if location:
            lat, lon, location_name = location
            args["lat"] = lat
            args["lon"] = lon
        else:
            args["q"] = event["args"]

        page = utils.http.request(URL_WEATHER, get_params=args, json=True)
        if page:
            if "weather" in page.data:
                if location_name:
                    location_str = location_name
                else:
                    location_parts = [page.data["name"]]
                    if "country" in page.data["sys"]:
                        location_parts.append(page.data["sys"]["country"])
                    location_str = ", ".join(location_parts)

                celsius = "%dC" % page.data["main"]["temp"]
                fahrenheit = "%dF" % ((page.data["main"]["temp"]*(9/5))+32)
                description = page.data["weather"][0]["description"].title()
                humidity = "%s%%" % page.data["main"]["humidity"]

                # wind speed is in metres per second - 3.6* for KMh
                wind_speed = 3.6*page.data["wind"]["speed"]
                wind_speed_k = "%sKMh" % round(wind_speed, 1)
                wind_speed_m = "%sMPh" % round(0.6214*wind_speed, 1)

                if not nickname == None:
                    event["stdout"].append_prefix("|%s" % nickname)
                event["stdout"].write(
                    "(%s) %s/%s | %s | Umidità: %s | Vento: %s/%s" % (
                    location_str, celsius, fahrenheit, description, humidity,
                    wind_speed_k, wind_speed_m))
            else:
                event["stderr"].write("Non sono presenti informazioni meteo per la località indicata")
        else:
            raise utils.EventsResultsError()
