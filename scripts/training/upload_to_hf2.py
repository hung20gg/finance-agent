import huggingface_hub
from huggingface_hub import login, hf_hub_download,  snapshot_download

login('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')


# repo_id = 'hung20gg/chat_vi'
# snapshot_download(repo_id = repo_id, repo_type="dataset", local_dir = 'data')

repo_id = 'hung20gg/qwen3-4b-sql'

folder_path = 'saves/qwen3-4b-test/lora/sft'
# snapshot_download(repo_id = repo_id, repo_type="model", local_dir = 'saves/gemma3-4b-it')


from huggingface_hub import upload_folder, hf_hub_download, snapshot_download

upload_folder(folder_path=folder_path, repo_id=repo_id, repo_type="model")