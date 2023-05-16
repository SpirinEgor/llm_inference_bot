from collections import namedtuple
from datetime import datetime
from os.path import exists

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


UserData = namedtuple("UserData", ["user_id", "name", "last_usage", "requests", "total_tokens"])


class GoogleSheetsWrapper:

    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
    TOKEN_FILE = "token.json"
    CREDENTIALS_FILE = "credentials.json"

    HEADER_VALUES = ["Id", "Name", "Last Usage", "Requests", "Total Tokens"]

    def __init__(self, spreadsheet_id: str):
        self.spreadsheet_id = spreadsheet_id
        creds = None
        if exists(self.TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(self.TOKEN_FILE, self.SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(self.CREDENTIALS_FILE, self.SCOPES)
                creds = flow.run_local_server(port=0)
            with open(self.TOKEN_FILE, "w") as f_token:
                f_token.write(creds.to_json())

        service = build("sheets", "v4", credentials=creds)
        self._sheet = service.spreadsheets()

    def add_sheet(self, sheet_name: str):
        request_body = {"requests": [{"addSheet": {"properties": {"title": sheet_name}}}]}
        self._sheet.batchUpdate(spreadsheetId=self.spreadsheet_id, body=request_body).execute()
        values = {"values": [self.HEADER_VALUES]}
        self._sheet.values().update(
            spreadsheetId=self.spreadsheet_id, range=f"{sheet_name}!A1:E1", body=values, valueInputOption="RAW"
        ).execute()

    def get_all_sheets(self):
        sheet_metadata = self._sheet.get(spreadsheetId=self.spreadsheet_id).execute()
        sheets = sheet_metadata.get("sheets", [])
        titles = [sheet.get("properties", {}).get("title", "[UNK]") for sheet in sheets]
        return titles

    def get_data(self) -> tuple[list[UserData], str]:
        current_month = datetime.now().strftime("%B")
        if current_month not in self.get_all_sheets():
            self.add_sheet(current_month)

        cells_range = f"{current_month}!A1:E"
        result = self._sheet.values().get(spreadsheetId=self.spreadsheet_id, range=cells_range).execute()
        values = [UserData(*it) for it in result.get("values", [])]

        return values, current_month

    def write_data(self, user_data: UserData, sheet_name: str, row_id: int):
        values = {"values": [user_data]}
        add_range = f"{sheet_name}!A{row_id}:E{row_id}"
        self._sheet.values().update(
            spreadsheetId=self.spreadsheet_id, range=add_range, body=values, valueInputOption="RAW"
        ).execute()

    def increase_user_usage(self, user_id: str | int, user_name: str, add_usage: int):
        all_data, month = self.get_data()
        row_id = len(all_data)
        requests, total_tokens = 1, add_usage

        user_id = str(user_id)
        for cur_row_id, user_data in enumerate(all_data):
            if user_data.user_id != user_id:
                continue
            total_tokens += int(user_data.total_tokens)
            requests += int(user_data.requests)
            row_id = cur_row_id
            break

        user_data = UserData(user_id, user_name, datetime.now().strftime("%d %b %H:%M:%S"), requests, total_tokens)
        self.write_data(user_data, month, row_id + 1)
