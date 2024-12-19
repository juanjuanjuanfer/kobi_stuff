import toml
import requests
import pandas as pd



TOML_FILE = '.streamlit/secrets.toml'
KPI_URL = "eu.kobotoolbox.org"

def get_secrets():
    with open(TOML_FILE, 'r') as file:
        secrets = toml.load(file)
    return secrets

def set_connection():
    secrets = get_secrets()
    kobo_url = secrets['kobo']['KOBO_API_TOKEN']

    headers = {
        "Authorization": f"Token {kobo_url}"
    }
    try:
        url = f"https://{KPI_URL}/api/v2/assets.json?limit=1000"
        response = requests.get(url, headers=headers)
        forms = response.json()["results"]
        forms_names = [form["name"] for form in forms]
        forms_ids = [form["uid"] for form in forms]
        result = {}
        for i in range(len(forms_names)):
            result[forms_names[i]] = forms_ids[i]
        return result   

    except Exception as e:
        print(f"Error: {e}")
        return None
    
def get_form_data(form_id):
    secrets = get_secrets()
    kobo_url = secrets['kobo']['KOBO_API_TOKEN']
    headers = {
        "Authorization": f"Token {kobo_url}"
    }

    form_url = f"https://{KPI_URL}/api/v2/assets/{form_id}.json"

    #obtain form structure
    response = requests.get(form_url, headers=headers)

    form_structure = response.json()

    survey = form_structure["content"]["survey"]

    survey_data = []
    for question in survey:
        question_id = question.get('name', question.get('$qpath', 'Unnamed'))
        qtype = question['type']
        label = question.get('label', [''])[0]
        required = question.get('required', False)
        depends_on = question.get('relevant', None)
        parent_group = question.get('$qpath', '').split('-')[0] if 'group_' in question.get('$qpath', '') else None
        
        survey_data.append({
            "Question ID": question_id,
            "Type": qtype,
            "Label": label,
            "Required": required,
            "Depends On": depends_on,
            "Parent Group": parent_group
        })

    # Create DataFrame
    df = pd.DataFrame(survey_data)
    choices_data = []
    for choice in form_structure["content"]['choices']:
        list_name = choice.get('list_name', None)
        option_name = choice.get('name', None)
        label = choice.get('label', [''])[0]  # First label in the list
        
        if list_name and option_name:  # Ensure valid data
            choices_data.append({
                "List Name": list_name,
                "Option Name": option_name,
                "Label": label
            })

    # Create a DataFrame
    df_2 = pd.DataFrame(choices_data)
    return df, df_2


def generate_create_table_queries(df1, df2=None, form_id="default"):
    # Include form_id in all table names to avoid name conflicts.

    type_map = {
        'text': 'TEXT',
        'integer': 'INT',
        'date': 'DATE',
        'time': 'TIME',
        'select_one': 'TEXT',
        'select_multiple': 'TEXT', # We'll store values in linking tables
        'start': 'TIMESTAMP',
        'end': 'TIMESTAMP',
        'image': 'TEXT', # Storing URL or path as TEXT
        'begin_repeat': None,
        'end_repeat': None
    }

    groups = df1[df1['Type'] == 'begin_repeat']['Question ID'].tolist()
    main_questions = df1[(df1['Parent Group'].isna()) & (~df1['Type'].isin(['begin_repeat', 'end_repeat']))]

    # Main table name includes the form_id
    main_table_name = f"submissions_{form_id}"
    main_fields = []
    for _, row in main_questions.iterrows():
        qid = row['Question ID']
        qtype = row['Type']
        sql_type = type_map.get(qtype, 'TEXT')
        if sql_type is not None:
            main_fields.append(f'"{qid}" {sql_type}')

    main_table_sql = f"CREATE TABLE {main_table_name} (\n  submission_id SERIAL PRIMARY KEY"
    if main_fields:
        main_table_sql += ",\n  " + ",\n  ".join(main_fields)
    main_table_sql += "\n);"

    queries = [main_table_sql]

    # Create a table for each repeating group with form_id included
    for g in groups:
        group_questions = df1[(df1['Parent Group'] == g) & (~df1['Type'].isin(['begin_repeat', 'end_repeat']))]
        group_table_name = f"{g.lower()}_{form_id}"
        group_fields = []
        for _, row in group_questions.iterrows():
            qid = row['Question ID']
            qtype = row['Type']
            sql_type = type_map.get(qtype, 'TEXT')
            if sql_type is not None and qtype != 'select_multiple':
                group_fields.append(f'"{qid}" {sql_type}')

        group_table_sql = f"CREATE TABLE {group_table_name} (\n  {group_table_name}_id SERIAL PRIMARY KEY,\n  submission_id INT REFERENCES {main_table_name}(submission_id)"
        if group_fields:
            group_table_sql += ",\n  " + ",\n  ".join(group_fields)
        group_table_sql += "\n);"
        queries.append(group_table_sql)

        # Linking tables for select_multiple inside groups
        select_mult_questions = group_questions[group_questions['Type'] == 'select_multiple']
        for _, row in select_mult_questions.iterrows():
            qid = row['Question ID']
            link_table_name = f"{group_table_name}_{qid}"
            link_table_sql = f"""CREATE TABLE {link_table_name} (
  {group_table_name}_id INT REFERENCES {group_table_name}({group_table_name}_id),
  value TEXT,
  PRIMARY KEY({group_table_name}_id, value)
);"""
            queries.append(link_table_sql)

    # Linking tables for main-level select_multiple questions
    main_select_mult = main_questions[main_questions['Type'] == 'select_multiple']['Question ID'].tolist()
    for qid in main_select_mult:
        link_table_name = f"{main_table_name}_{qid}"
        link_table_sql = f"""CREATE TABLE {link_table_name} (
  submission_id INT REFERENCES {main_table_name}(submission_id),
  value TEXT,
  PRIMARY KEY(submission_id, value)
);"""
        queries.append(link_table_sql)

    # Removed creation of choice tables

    return "\n\n".join(queries)

# Example usage (assuming df1 and df2 are defined):
# sql_queries = generate_create_table_queries(df1, df2)
# print(sql_queries)

import requests
import json

def generate_insert_queries(df1, df2, asset_data_json, kpi_url, asset, token, form_id="default"):
    type_map = {
        'text': 'TEXT',
        'integer': 'INT',
        'date': 'DATE',
        'time': 'TIME',
        'select_one': 'TEXT',
        'select_multiple': 'TEXT',  # stored separately in linking tables
        'start': 'TIMESTAMP',
        'end': 'TIMESTAMP',
        'image': 'TEXT',
        'begin_repeat': None,
        'end_repeat': None
    }

    if asset_data_json is None:
        url = f"https://{kpi_url}/api/v2/assets/{asset}/data.json"
        headers = {"Authorization": f"Token {token}"}
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        asset_data_json = resp.json()

    groups = df1[df1['Type'] == 'begin_repeat']['Question ID'].tolist()
    main_questions = df1[(df1['Parent Group'].isna()) & (~df1['Type'].isin(['begin_repeat', 'end_repeat']))]

    main_table_name = f"submissions_{form_id}"

    # Build group structure as in creation
    group_tables = {}
    for g in groups:
        group_questions = df1[(df1['Parent Group'] == g) & (~df1['Type'].isin(['begin_repeat', 'end_repeat']))]
        group_fields = group_questions[group_questions['Type'] != 'select_multiple']['Question ID'].tolist()
        group_s_mult = group_questions[group_questions['Type'] == 'select_multiple']['Question ID'].tolist()
        group_tables[g] = {
            'fields': group_fields,
            'select_multiple': group_s_mult
        }

    main_select_mult = main_questions[main_questions['Type'] == 'select_multiple']['Question ID'].tolist()

    def format_value(val):
        if val is None:
            return "NULL"
        val_str = str(val).replace("'", "''")
        return f"'{val_str}'"

    insert_statements = []

    for submission in asset_data_json.get('results', []):
        # Insert main record
        main_cols = []
        main_vals = []
        for _, row in main_questions.iterrows():
            qid = row['Question ID']
            qtype = row['Type']
            if qtype in ['begin_repeat', 'end_repeat']:
                continue
            sql_type = type_map.get(qtype, 'TEXT')
            if sql_type is None:
                continue

            val = submission.get(qid, None)
            if qid in main_select_mult:
                # handled separately in linking tables
                pass
            else:
                if val is None:
                    main_cols.append(f'"{qid}"')
                    main_vals.append("NULL")
                else:
                    main_cols.append(f'"{qid}"')
                    main_vals.append(format_value(val))

        if main_cols:
            insert_main = f"INSERT INTO {main_table_name} ({', '.join(main_cols)}) VALUES ({', '.join(main_vals)});\n"
        else:
            insert_main = f"INSERT INTO {main_table_name} DEFAULT VALUES;\n"

        insert_statements.append(insert_main)

        # Handle main-level select_multiple
        for qid in main_select_mult:
            val = submission.get(qid, None)
            if val:
                opts = val.split()
                link_table_name = f"{main_table_name}_{qid}"
                for o in opts:
                    insert_statements.append(
                        f"INSERT INTO {link_table_name} (submission_id, value) VALUES (CURRVAL('{main_table_name}_submission_id_seq'), {format_value(o)});\n"
                    )

        # Handle groups
        for g in groups:
            group_table_name = f"{g.lower()}_{form_id}"
            group_info = group_tables[g]
            group_data = submission.get(g, None)
            if group_data and isinstance(group_data, list):
                for gd in group_data:
                    group_cols = ["submission_id"]
                    group_vals = [f"CURRVAL('{main_table_name}_submission_id_seq')"]

                    for field in group_info['fields']:
                        val = gd.get(field, None)
                        if val is None:
                            group_cols.append(f'"{field}"')
                            group_vals.append("NULL")
                        else:
                            group_cols.append(f'"{field}"')
                            group_vals.append(format_value(val))

                    insert_group = f"INSERT INTO {group_table_name} ({', '.join(group_cols)}) VALUES ({', '.join(group_vals)});\n"
                    insert_statements.append(insert_group)

                    # group-level select_multiple
                    for s_mult_field in group_info['select_multiple']:
                        val = gd.get(s_mult_field, None)
                        if val:
                            opts = val.split()
                            link_table_name = f"{group_table_name}_{s_mult_field}"
                            for o in opts:
                                insert_statements.append(
                                    f"INSERT INTO {link_table_name} ({group_table_name}_id, value) VALUES (CURRVAL('{group_table_name}_{group_table_name}_id_seq'), {format_value(o)});\n"
                                )

    return "".join(insert_statements)

