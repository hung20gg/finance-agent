import os
from dotenv import load_dotenv

import huggingface_hub
from huggingface_hub import login, hf_hub_download,  snapshot_download
load_dotenv

login(os.getenv('HF_TOKEN'))


#repo_id = 'hung20gg/vi_raw'
# snapshot_download(repo_id = repo_id, repo_type="dataset", local_dir = 'data')

# repo_id = 'hung20gg/gemma3'

repo_id = 'hung20gg/qwen3-sql-grpo'

# folder_path = 'saves/gemma3-4b-it/lora'
# snapshot_download(repo_id = repo_id, repo_type="model", local_dir = 'models/')


snapshot_download(
    repo_id=repo_id,
    repo_type="model",          # or "dataset"
    allow_patterns="global_step_240/*",
    local_dir = 'models/qwen3-1.7b-grpo'

)

# folder_path = 'saves'


# from huggingface_hub import upload_folder, hf_hub_download, snapshot_download

# upload_folder(folder_path=folder_path, repo_id=repo_id, repo_type="model")