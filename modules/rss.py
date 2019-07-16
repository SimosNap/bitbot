#--depends-on config
#--depends-on shorturl
	
import time
from src import ModuleManager, utils
import feedparser

RSS_INTERVAL = 60 # 1 minute

@utils.export("botset", utils.IntSetting("rss-interval",
    "Interval (in seconds) between RSS polls", example="600"))
@utils.export("channelset", utils.BoolSetting("rss-shorten",
	    "Whether or not to shorten RSS urls"))
class Module(ModuleManager.BaseModule):
    _name = "RSS"
    def on_load(self):
        self.timers.add("rss", self.bot.get_setting("rss-interval",
            RSS_INTERVAL))

    def _format_entry(self, server, feed_title, entry, shorten):
	        title = entry["title"]
	
	        author = entry.get("author", None)
	        author = " by %s" % author if author else ""
	
	        link = entry.get("link", None)
	        if shorten:
	            link = self.exports.get_one("shorturl")(server, link)
	        link = " - %s" % link if link else ""
	
	        feed_title_str = "%s: " % feed_title if feed_title else ""
	
	        return "%s%s%s%s" % (feed_title_str, title, author, link)
	        

    @utils.hook("timer.rss")
    def timer(self, event):
        start_time = time.monotonic()
        self.log.trace("Polling RSS feeds")

        event["timer"].redo()
        hook_settings = self.bot.database.channel_settings.find_by_setting(
            "rss-hooks")
        hooks = {}
        for server_id, channel_name, urls in hook_settings:
            server = self.bot.get_server_by_id(server_id)
            if server and channel_name in server.channels:
                channel = server.channels.get(channel_name)
                for url in urls:
                    if not url in hooks:
                        hooks[url] = []
                    hooks[url].append((server, channel))

        pages = utils.http.request_many(hooks.keys())

        for url, channels in hooks.items():
            if not url in pages:
                # async url get failed
                continue

            feed = feedparser.parse(pages[url].data)
            feed_title = feed["feed"].get("title", None)

            for server, channel in channels:
                seen_ids = channel.get_setting("rss-seen-ids-%s" % url, [])
                new_ids = []
                valid = 0
                for entry in feed["entries"][::-1]:
                    entry_id = entry.get("id", entry["link"])
                    if entry_id in seen_ids:
                        new_ids.append(entry_id)
                        continue

                    if valid == 3:
                        continue
                    valid += 1

                    shorten = channel.get_setting("rss-shorten", False)
                    output = self._format_entry(server, feed_title, entry,
                        shorten)
	           
                    self.events.on("send.stdout").call(target=channel,
                        module_name="RSS", server=server, message=output)
                    new_ids.append(entry_id)

                channel.set_setting("rss-seen-ids-%s" % url, new_ids)

        total_milliseconds = (time.monotonic() - start_time) * 1000
        self.log.trace("Polled RSS feeds in %fms", [total_milliseconds])

    def _check_url(self, url):
        try:
            data = utils.http.request(url)
            feed = feedparser.parse(data.data)
        except Exception as e:
            self.log.warn("failed to parse RSS %s", [url], exc_info=True)
            feed = None
        if not feed or not feed["feed"]:
            return None

        entry_ids = []
        for entry in feed["entries"]:
            entry_ids.append(entry.get("id", entry["link"]))
        return entry_ids

    @utils.hook("received.command.rss", min_args=1, channel_only=True)
    def rss(self, event):
        """
        :help: Modifica configurazione RSS / Atom per il canale corrente
        :usage: list
        :usage: add <url>
        :usage: remove <url>
        :permission: rss
        """
        changed = False
        message = None

        rss_hooks = event["target"].get_setting("rss-hooks", [])

        subcommand = event["args_split"][0].lower()
        if subcommand == "list":
            event["stdout"].write("RSS hooks: %s" % ", ".join(rss_hooks))
        elif subcommand == "add":
            if not len(event["args_split"]) > 1:
                raise utils.EventError("Si prega di fornire un URL")

            url = utils.http.url_sanitise(event["args_split"][1])
            if url in rss_hooks:
                raise utils.EventError("Questo URL è già stato monitorato")

            seen_ids = self._check_url(url)
            if seen_ids == None:
                raise utils.EventError("Impossibile leggere il feed")
            event["target"].set_setting("rss-seen-ids-%s" % url, seen_ids)

            rss_hooks.append(url)
            changed = True
            message = "Added RSS feed"
        elif subcommand == "remove":
            if not len(event["args_split"]) > 1:
                raise utils.EventError("Si prega di fornire un URL")

            url = utils.http.url_sanitise(event["args_split"][1])
            if not url in rss_hooks:
                raise utils.EventError("Non sto monitorando questo URL")
            rss_hooks.remove(url)
            changed = True
            message = "Feed RSS Rimosso"
        else:
            raise utils.EventError("Comando sconosciuto'%s'" % subcommand)

        if changed:
            if rss_hooks:
                event["target"].set_setting("rss-hooks", rss_hooks)
            else:
                event["target"].del_setting("rss-hooks")
            event["stdout"].write(message)
