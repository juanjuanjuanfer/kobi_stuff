import requests
from dotenv import load_dotenv
import os
import json

load_dotenv()
KOBO_API_TOKEN = os.environ.get("KOBO_API_TOKEN")
KPI_URL = "eu.kobotoolbox.org"

print("KOBOTOOLBOX FORMULARIOS\n")
limit = int(input("Ingrese el numero maximo de formularios a mostrar: "))
url = f"https://{KPI_URL}/api/v2/assets.json?limit={limit}"

headers = {

    "Authorization": f"Token {KOBO_API_TOKEN}"

}

response = requests.get(url, headers=headers)

# get forms names and ids
forms = response.json()["results"]
forms_names = [form["name"] for form in forms]
forms_ids = [form["uid"] for form in forms]
print(f"Formularios:\n")
for i in range(len(forms_names)):
    print(f"{i+1}. {forms_names[i]}, id: {forms_ids[i]}")


# get form data
form_id = input("Ingrese el id del formulario: ")
form_url = f"https://{KPI_URL}/api/v2/assets/{form_id}.json"

#obtain form structure
response = requests.get(form_url, headers=headers)
form_structure = response.json()
with open("form_structure.json", "w") as file:
    json.dump(form_structure, file, indent=4)