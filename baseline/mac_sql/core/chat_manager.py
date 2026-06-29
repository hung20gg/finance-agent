from baseline.mac_sql.core.agents import Decomposer, Refiner, Selector
from baseline.mac_sql.core.const import DECOMPOSER_NAME, MAX_ROUND, REFINER_NAME, SELECTOR_NAME, SYSTEM_NAME
from baseline.mac_sql.core.db import PostgresDatabase

from baseline.mac_sql.core.llm import init_log_path


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
        # Follow Algorithm 1 from the original MAC-SQL paper:
        # optional Selector -> Decomposer -> Refiner retry loop.
        self.selector = Selector(
            database=self.database,
            model_name=self.model_name,
            without_selector=without_selector,
        )
        self.decomposer = Decomposer(model_name=self.model_name)
        self.refiner = Refiner(database=self.database, model_name=self.model_name)
        init_log_path(log_path)

    def _run_selector(self, message: dict):
        if message["send_to"] == SELECTOR_NAME:
            self.selector.talk(message)

    def _run_decomposer(self, message: dict):
        if message["send_to"] == DECOMPOSER_NAME:
            self.decomposer.talk(message)

    def _run_refiner(self, message: dict):
        if message["send_to"] == REFINER_NAME:
            self.refiner.talk(message)

    def start(self, user_message: dict):
        """Run one paper-faithful MAC-SQL session for a single query.

        The original method is sequential per query, not parallel:
        Selector -> Decomposer -> Refiner, with bounded refine retries.
        """
        if user_message["send_to"] == SYSTEM_NAME:
            user_message["send_to"] = SELECTOR_NAME

        self._run_selector(user_message)
        self._run_decomposer(user_message)

        refine_count = 0
        while user_message["send_to"] == REFINER_NAME and refine_count < MAX_ROUND:
            self._run_refiner(user_message)
            refine_count += 1
