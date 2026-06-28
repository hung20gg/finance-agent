from core.agents import Decomposer, Refiner, Selector
from core.const import DECOMPOSER_NAME, MAX_ROUND, REFINER_NAME, SELECTOR_NAME, SYSTEM_NAME
from core.db import PostgresDatabase

from core.llm import init_log_path


class ChatManager:
    def __init__(
        self,
        postgres_url: str,
        schema: str,
        log_path: str,
        model_name: str,
        include_tables=None,
        exclude_tables=None,
        without_selector: bool = False,
    ):
        self.log_path = log_path
        self.model_name = model_name
        self.database = PostgresDatabase(
            postgres_url=postgres_url,
            schema=schema,
            include_tables=include_tables,
            exclude_tables=exclude_tables,
        )
        self.chat_group = [
            Selector(
                database=self.database,
                model_name=self.model_name,
                without_selector=without_selector,
            ),
            Decomposer(model_name=self.model_name),
            Refiner(database=self.database, model_name=self.model_name),
        ]
        init_log_path(log_path)

    def _chat_single_round(self, message: dict):
        for agent in self.chat_group:
            if message["send_to"] == agent.name:
                agent.talk(message)

    def start(self, user_message: dict):
        if user_message["send_to"] == SYSTEM_NAME:
            user_message["send_to"] = SELECTOR_NAME
        for _ in range(MAX_ROUND):
            self._chat_single_round(user_message)
            if user_message["send_to"] == SYSTEM_NAME:
                break
