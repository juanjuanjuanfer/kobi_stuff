from dotenv import load_dotenv
import requests
import json
import os


class APIHandler:

    """Manage KoboToolbox API requests"""

    def __init__(self):

        load_dotenv()

        self.base_url = "https://eu.kobotoolbox.org"

        self.token = os.getenv("KOBO_API_TOKEN")

        self.headers = {
            "Authorization": f"Token {self.token}"
        }

    def fetch_data(self, endpoint: str) -> dict:

        """Fetch data for given endpoint"""

        url = f"{self.base_url}/{endpoint}"

        response = requests.get(url, headers=self.headers)

        response.raise_for_status()

        return response.json()



class KoboAPI(APIHandler):

    def __init___(self):

        super().__init__()

        self.endpoint = ""

        self.limit = ""

        self.forms = {}

    def get_forms(self, endpoint, limit: int = 1000):

        self.endpoint = endpoint

        self.limit = limit

        self.endpoint = f"{self.endpoint}?limit={self.limit}"

        self.forms = self.fetch_data(self.endpoint)["results"]



class KoboForm(APIHandler):

    def __init__(self):

        super().__init__()

        self.form_id = ""

        self.form_endpoint = f"api/v2/assets/{self.form_id}.json"

        self.form_data = {}

        self.base_url = "https://eu.kobotoolbox.org"


    def fetch_form_data(self, store: bool = False, endpoint: str= None) -> dict:

        if endpoint is not None:

            self.form_endpoint = endpoint

        form_data = self.fetch_data(self.form_endpoint)

        if store:

            self.form_data = form_data

        else:

            return form_data


    def set_form_id(self, form_id: str, auto_fetch: bool = False):

        self.form_id = form_id

        self.form_endpoint = f"api/v2/assets/{self.form_id}.json"

        if auto_fetch:

            self.fetch_form_data(store=True)


    def save_data(self, path="data"):

        path = f"{path}.json"

        with open(path, "w") as file:

            json.dump(self.form_data, file, indent=4)



class ManageData:

    def __init__(self, data: dict):

        self.data = data

        self.url = data["url"]