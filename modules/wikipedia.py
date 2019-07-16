#--depends-on commands

from src import ModuleManager, utils

URL_WIKIPEDIA = "https://it.wikipedia.org/w/api.php"

class Module(ModuleManager.BaseModule):
    @utils.hook("received.command.wi", alias_of="wiki")
    @utils.hook("received.command.wiki", alias_of="wikipedia")
    @utils.hook("received.command.wikipedia", min_args=1)
    def wikipedia(self, event):
        """
        :help: Ottieni informazioni da wikipedia
        :usage: <term>
        """
        page = utils.http.request(URL_WIKIPEDIA, get_params={
            "action": "query", "prop": "extracts",
            "titles": event["args"], "exintro": "",
            "explaintext": "", "exchars": "500",
            "redirects": "", "format": "json"}, json=True)
        if page:
            pages = page.data["query"]["pages"]
            article = list(pages.items())[0][1]
            if not "missing" in article:
                title, info = article["title"], article["extract"]
                info = info.replace("\n\n", " ").split("\n")[0]
                event["stdout"].write("%s: %s" % (title, info))
            else:
                event["stderr"].write("No results found")
        else:
            raise utils.EventsResultsError()

