#
# Copyright (c) 2022 Airbyte, Inc., all rights reserved.
#

from abc import ABC, abstractmethod
from typing import Any, Iterable, Mapping, MutableMapping,  List,Optional
from airbyte_cdk.models import SyncMode

import requests
from datetime import datetime, timedelta    
from airbyte_cdk.sources.streams.http import HttpStream
from airbyte_cdk.sources.streams import IncrementalMixin
from airbyte_cdk.sources.utils.transform import TransformConfig, TypeTransformer
from source_facebook_pages.metrics import PAGE_FIELDS, LEADGEN_FORMS_FIELDS, LEAD_FIELDS


class FacebookPagesStream(HttpStream, ABC):
    url_base = "https://graph.facebook.com/v15.0/"
    primary_key = "id"
    data_field = "data"
    transformer = TypeTransformer(TransformConfig.DefaultSchemaNormalization)

    def __init__(
        self,
        access_token: str = None,
        page_id: str = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._access_token = access_token
        self._page_id = page_id

    @property
    def path_param(self):
        return self.name[:-1]

    def next_page_token(self, response: requests.Response) -> Optional[Mapping[str, Any]]:
        data = response.json()

        if not data.get("data") or not data.get("paging"):
            return {}

        return {
            "limit": 100,
            "after": data.get("paging", {}).get("cursors", {}).get("after"),
        }

    def request_params(
        self,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, any] = None,
        next_page_token: Mapping[str, Any] = None,
    ) -> MutableMapping[str, Any]:
        next_page_token = next_page_token or {}
        params = {"access_token": self._access_token, **next_page_token}

        return params

    def parse_response(self, response: requests.Response, **kwargs) -> Iterable[Mapping]:
        if not self.data_field:
            yield response.json()

        records = response.json().get(self.data_field, [])

        for record in records:
            yield record

class Page(FacebookPagesStream):
    """
    API docs: https://developers.facebook.com/docs/graph-api/reference/page/,
    """

    data_field = ""

    def path(self, **kwargs) -> str:
        return self._page_id

    def next_page_token(self, response: requests.Response) -> Optional[Mapping[str, Any]]:
        return None

    def request_params(self, **kwargs) -> MutableMapping[str, Any]:
        params = super().request_params(**kwargs)
        # we have to define which fields will return from Facebook API
        # because FB API doesn't provide opportunity to get fields dynamically without delays
        # so in PAGE_FIELDS we define fields that user can get from API
        params["fields"] = PAGE_FIELDS

        return params

class LeadgenForms(FacebookPagesStream):
    """
    API docs: https://developers.facebook.com/docs/graph-api/reference/page/leadgen_forms/,
    """

    def path(self, **kwargs) -> str:
        return f"{self._page_id}/leadgen_forms"

    def next_page_token(self, response: requests.Response) -> Optional[Mapping[str, Any]]:
        return None

    def request_params(self, **kwargs) -> MutableMapping[str, Any]:
        params = super().request_params(**kwargs)
        # we have to define which fields will return from Facebook API
        # because FB API doesn't provide opportunity to get fields dynamically without delays
        # so in LEADGEN_FORMS_FIELDS we define fields that user can get from API
        params["fields"] = LEADGEN_FORMS_FIELDS

        return params


class Leads(FacebookPagesStream, IncrementalMixin):

    """
    API docs: https://developers.facebook.com/docs/marketing-api/guides/lead-ads/retrieving/#bulk-read
    """
    state_checkpoint_interval = 50
    primary_key = "id"
    cursor_field = "created_time"
    start_date = ""

    def path(
        self,
        *,
        stream_state: Mapping[str, Any] = None,
        stream_slice: Mapping[str, Any] = None,
        next_page_token: Mapping[str, Any] = None,
    ) -> str:
        return f"{stream_slice['form_id']}/leads"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.forms = LeadgenForms(**kwargs)
        self._cursor_value = None

    def stream_slices(
        self, *, sync_mode: SyncMode, cursor_field: List[str] = None, stream_state: Mapping[str, Any] = None
    ) -> Iterable[Optional[Mapping[str, Any]]]:
        slices = []
        seen = set()
        # To get submissions for all forms date filtering has to be disabled
        for form in self.forms.read_records(sync_mode):
            if form['id'] not in seen:
                seen.add(form['id'])
                slices.append({"form_id": form['id']})
        return slices

    def read_records(self, *args, **kwargs) -> Iterable[Mapping[str, Any]]:
        for record in super().read_records(*args, **kwargs):
            date = record[self.cursor_field]
            if self._cursor_value:
                self._cursor_value = max(self._cursor_value, date)
            else:
                self._cursor_value = date
            yield record

    def request_params(self, **kwargs) -> MutableMapping[str, Any]:
        params = super().request_params(**kwargs)
        if self.start_date != "":
            str_time = datetime.strptime(self.start_date, "%Y-%m-%dT%H:%M:%S%z").timestamp()
            params["filtering"] = "[{'field':'time_created','operator':'GREATER_THAN','value': " + str( str_time ) + "}]"
        
        # we have to define which fields will return from Facebook API
        # because FB API doesn't provide opportunity to get fields dynamically without delays
        # so in PAGE_FIELDS we define fields that user can get from API
        params["fields"] = LEAD_FIELDS

        return params

    @property
    def state(self) -> Mapping[str, Any]:
        return {self.cursor_field: self._cursor_value}
    
    @state.setter
    def state(self, value: Mapping[str, Any]):
        if self.cursor_field in value and value[self.cursor_field]:
            #To ensure the date is less than the most recent record, just reduce by one day
            cursor_date_time = datetime.strptime(value[self.cursor_field], "%Y-%m-%dT%H:%M:%S%z") - timedelta(days=1)
            self._cursor_value = cursor_date_time.strftime("%Y-%m-%dT%H:%M:%S%z")
            self.start_date = self._cursor_value
