# -*- coding: utf-8 -*-
from copy import deepcopy

from baseline.mac_sql.core.const import *
from baseline.mac_sql.core.db import PostgresDatabase, normalize_postgres_sql
from baseline.mac_sql.core.utils import parse_json, parse_qa_pairs, parse_sql_from_string


POSTGRES_DIALECT_GUIDE = """
【PostgreSQL dialect rules】
- Generate valid PostgreSQL only.
- Never use backticks. Use unquoted snake_case identifiers by default.
- If an identifier must be quoted, use double quotes.
- Prefer explicit casts like CAST(... AS NUMERIC) when needed.
- DO NOT generate any comment in SQL Statements.
""".strip()


class BaseAgent:
    def __init__(self, llm) -> None:
        self.llm = llm

    @staticmethod
    def _update_token_usage(message: dict, response: dict) -> None:
        if not isinstance(response, dict):
            return

        prompt_tokens = int(response.get("prompt_tokens") or 0)
        completion_tokens = int(response.get("completion_tokens") or 0)

        message["total_prompt_tokens"] = int(message.get("total_prompt_tokens") or 0) + prompt_tokens
        message["total_output_tokens"] = int(message.get("total_output_tokens") or 0) + completion_tokens
        message["total_tokens"] = message["total_prompt_tokens"] + message["total_output_tokens"]

    def _invoke_llm(self, prompt: str, message: dict) -> str:
        detail_kwargs = {}
        if getattr(self.llm, "model_type", "") != "gemini":
            detail_kwargs["detail"] = True

        response = self.llm.invoke(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            **detail_kwargs,
        )
        if response is None:
            raise RuntimeError(f"LLM returned no response for model {self.llm.model_name}")
        if isinstance(response, dict):
            self._update_token_usage(message, response)
            return response.get("content", "")
        return str(response)

    def talk(self, message: dict):
        raise NotImplementedError()


class Selector(BaseAgent):
    name = SELECTOR_NAME
    description = "Get database description and extract relevant tables and columns."

    def __init__(
        self,
        database: PostgresDatabase,
        llm,
        without_selector: bool = False,
    ):
        super().__init__(llm)
        self.database = database
        self.db2infos = {}
        self._message = {}
        self.without_selector = without_selector

    def _build_table_schema_list_str(self, table_name, new_columns_desc, new_columns_val):
        schema_desc_str = f"# Table: {table_name}\n"
        extracted_column_infos = []
        for (col_name, full_col_name, col_extra_desc), (_, col_values_str) in zip(
            new_columns_desc, new_columns_val
        ):
            col_extra_desc = (
                "And " + str(col_extra_desc)
                if col_extra_desc != "" and str(col_extra_desc) != "nan"
                else ""
            )
            col_extra_desc = col_extra_desc[:100]

            col_line_text = "  ("
            col_line_text += f"{col_name},"

            if full_col_name != "":
                col_line_text += f" {full_col_name.strip()}."
            if col_values_str != "":
                col_line_text += f" Value examples: {col_values_str}."
            if col_extra_desc != "":
                col_line_text += f" {col_extra_desc}"
            col_line_text += "),"
            extracted_column_infos.append(col_line_text)
        schema_desc_str += "[\n" + "\n".join(extracted_column_infos).strip(",") + "\n]\n"
        return schema_desc_str

    def _get_db_desc_str(self, db_id: str, extracted_schema: dict):
        if self.db2infos.get(db_id, {}) == {}:
            self.db2infos[db_id] = self.database.load_schema_info(db_id)
        db_info = self.db2infos[db_id]
        desc_info = db_info["desc_dict"]
        value_info = db_info["value_dict"]
        pk_info = db_info["pk_dict"]
        fk_info = db_info["fk_dict"]

        schema_desc_str = ""
        db_fk_infos = []
        chosen_db_schem_dict = {}

        for (table_name, columns_desc), (_, columns_val), (_, cur_fk_info), (_, cur_pk_info) in zip(
            desc_info.items(), value_info.items(), fk_info.items(), pk_info.items()
        ):
            table_decision = extracted_schema.get(table_name, "")

            all_columns = [name for name, _, _ in columns_desc]
            important_keys = list(cur_pk_info) + [name for name, _, _ in cur_fk_info]

            if table_decision == "drop_all":
                new_columns_desc = deepcopy(columns_desc[:6])
                new_columns_val = deepcopy(columns_val[:6])
            elif table_decision in ["keep_all", ""]:
                new_columns_desc = deepcopy(columns_desc)
                new_columns_val = deepcopy(columns_val)
            else:
                new_columns_desc = []
                new_columns_val = []
                appended = []
                for idx, col in enumerate(all_columns):
                    if col in important_keys or col in table_decision:
                        new_columns_desc.append(columns_desc[idx])
                        new_columns_val.append(columns_val[idx])
                        appended.append(col)
                if len(all_columns) > 6 and len(new_columns_val) < 6:
                    for idx, col in enumerate(all_columns):
                        if len(appended) >= 6:
                            break
                        if col not in appended:
                            new_columns_desc.append(columns_desc[idx])
                            new_columns_val.append(columns_val[idx])
                            appended.append(col)

            chosen_db_schem_dict[table_name] = [col_name for col_name, _, _ in new_columns_desc]
            schema_desc_str += self._build_table_schema_list_str(
                table_name, new_columns_desc, new_columns_val
            )

            for col_name, to_table, to_col in cur_fk_info:
                fk_link_str = f'{table_name}."{col_name}" = {to_table}."{to_col}"'
                if fk_link_str not in db_fk_infos:
                    db_fk_infos.append(fk_link_str)

        return schema_desc_str.strip(), "\n".join(db_fk_infos).strip(), chosen_db_schem_dict

    def _is_need_prune(self, db_id: str):
        db_info = self.db2infos[db_id]
        stats = db_info["stats"]
        if stats["avg_column_count"] <= 6 and stats["total_column_count"] <= 30:
            return False
        return True

    def _prune(self, db_id: str, query: str, db_schema: str, db_fk: str, evidence: str = None) -> dict:
        prompt = selector_template.format(
            db_id=db_id,
            query=query,
            evidence=evidence or "",
            desc_str=db_schema,
            fk_str=db_fk,
        )
        prompt += "\n\n" + POSTGRES_DIALECT_GUIDE
        reply = self._invoke_llm(prompt, self._message)
        return parse_json(reply)

    def talk(self, message: dict):
        if message["send_to"] != self.name:
            return
        self._message = message
        db_id = message.get("db_id")
        ext_sch = message.get("extracted_schema", {})
        query = message.get("query")
        evidence = message.get("evidence")

        db_schema, db_fk, chosen_db_schem_dict = self._get_db_desc_str(db_id=db_id, extracted_schema=ext_sch)
        need_prune = self._is_need_prune(db_id)
        if self.without_selector:
            need_prune = False

        if ext_sch == {} and need_prune:
            try:
                raw_extracted_schema_dict = self._prune(
                    db_id=db_id,
                    query=query,
                    db_schema=db_schema,
                    db_fk=db_fk,
                    evidence=evidence,
                )
            except Exception:
                raw_extracted_schema_dict = {}

            db_schema_str, db_fk, chosen_db_schem_dict = self._get_db_desc_str(
                db_id=db_id,
                extracted_schema=raw_extracted_schema_dict,
            )
            message["extracted_schema"] = raw_extracted_schema_dict
            message["chosen_db_schem_dict"] = chosen_db_schem_dict
            message["desc_str"] = db_schema_str
            message["fk_str"] = db_fk
            message["pruned"] = True
            message["send_to"] = DECOMPOSER_NAME
        else:
            message["chosen_db_schem_dict"] = chosen_db_schem_dict
            message["desc_str"] = db_schema
            message["fk_str"] = db_fk
            message["pruned"] = False
            message["send_to"] = DECOMPOSER_NAME


class Decomposer(BaseAgent):
    name = DECOMPOSER_NAME
    description = "Decompose the question and generate SQL."

    def __init__(self, llm):
        super().__init__(llm)
        self._message = {}

    def talk(self, message: dict):
        if message["send_to"] != self.name:
            return
        self._message = message
        query = message.get("query")
        evidence = message.get("evidence")
        schema_info = message.get("desc_str")
        fk_info = message.get("fk_str")

        prompt = decompose_template_bird.format(
            query=query,
            desc_str=schema_info,
            fk_str=fk_info,
            evidence=evidence or "",
        )
        prompt += "\n\n" + POSTGRES_DIALECT_GUIDE
        reply = self._invoke_llm(prompt, self._message).strip()

        try:
            res = parse_sql_from_string(reply)
        except Exception as exc:
            res = f"error: {str(exc)}"

        message["final_sql"] = normalize_postgres_sql(res)
        message["qa_pairs"] = parse_qa_pairs(reply)
        message["fixed"] = False
        message["send_to"] = REFINER_NAME


class Refiner(BaseAgent):
    name = REFINER_NAME
    description = "Execute SQL and perform validation."

    def __init__(self, database: PostgresDatabase, llm):
        super().__init__(llm)
        self.database = database
        self._message = {}

    def _execute_sql(self, sql_text: str) -> dict:
        return self.database.execute_sql(sql_text)

    def _is_need_refine(self, exec_result: dict):
        data = exec_result.get("data")
        if data is not None:
            if len(data) == 0:
                exec_result["db_error"] = "no data selected"
                return True
            for row in data:
                values = row.values() if isinstance(row, dict) else row
                for value in values:
                    if value is None:
                        exec_result["db_error"] = "result contains NULL values; add IS NOT NULL if appropriate"
                        return True
            return False
        return True

    def _refine(self, query: str, evidence: str, schema_info: str, fk_info: str, error_info: dict) -> str:
        prompt = refiner_template.format(
            query=query,
            evidence=evidence or "",
            desc_str=schema_info,
            fk_str=fk_info,
            sql=error_info.get("sql"),
            PostgreSQL_error=error_info.get("db_error"),
            exception_class=error_info.get("exception_class"),
        )
        prompt += "\n\n" + POSTGRES_DIALECT_GUIDE
        reply = self._invoke_llm(prompt, self._message)
        return normalize_postgres_sql(parse_sql_from_string(reply))

    def talk(self, message: dict):
        if message["send_to"] != self.name:
            return
        self._message = message

        old_sql = normalize_postgres_sql(message.get("pred", message.get("final_sql", "")))
        if "error" in old_sql.lower():
            message["try_times"] = message.get("try_times", 0) + 1
            message["pred"] = old_sql
            message["send_to"] = SYSTEM_NAME
            return

        is_timeout = False
        try:
            error_info = self._execute_sql(old_sql)
        except Exception:
            is_timeout = True
            error_info = {}

        is_need = self._is_need_refine(error_info) if not is_timeout else False
        if not is_need:
            message["execution_result"] = error_info.get("data", [])

        if not is_need or is_timeout:
            message["try_times"] = message.get("try_times", 0) + 1
            message["pred"] = old_sql
            message["send_to"] = SYSTEM_NAME
        else:
            new_sql = self._refine(
                query=message.get("query"),
                evidence=message.get("evidence"),
                schema_info=message.get("desc_str"),
                fk_info=message.get("fk_str"),
                error_info=error_info,
            )
            message["try_times"] = message.get("try_times", 0) + 1
            message["pred"] = new_sql
            message["fixed"] = True
            message["send_to"] = REFINER_NAME
