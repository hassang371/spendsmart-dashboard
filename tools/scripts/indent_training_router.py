import sys
import re

def process_file_training(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # Add import
    import_stmt = "from apps.api.core.idempotency import get_idempotency_key, with_idempotency\n"
    if "get_idempotency_key" not in content:
        content = content.replace("from supabase import Client\n", "from supabase import Client\n" + import_stmt)

    # Wrap upload endpoint
    upload_sig_target = """async def upload_training_data(
    file: UploadFile = File(...),
    password: Optional[str] = Form(None),
    user_id: str = Depends(get_current_user_id),
    client: Client = Depends(get_user_client),
):
    \"\"\"Upload transaction file, ingest into DB, and trigger adapter training.\"\"\""""
    upload_sig_replacement = """async def upload_training_data(
    file: UploadFile = File(...),
    password: Optional[str] = Form(None),
    user_id: str = Depends(get_current_user_id),
    client: Client = Depends(get_user_client),
    idempotency_key: str | None = Depends(get_idempotency_key),
):
    \"\"\"Upload transaction file, ingest into DB, and trigger adapter training.\"\"\"
    async def _execute():"""

    # Wrap train endpoint
    train_sig_target = """async def train_adapter_async(
    epochs: int = 5,
    learning_rate: float = 1e-3,
    user_id: str = Depends(get_current_user_id),
    client: Client = Depends(get_user_client),
):
    \"\"\"Start async adapter training job. Returns immediately with job_id.

    v2: Trains the user's Linear Adapter from categorized transactions.
    The frozen MiniLM base model is never retrained.
    \"\"\""""
    
    train_sig_replacement = """async def train_adapter_async(
    epochs: int = 5,
    learning_rate: float = 1e-3,
    user_id: str = Depends(get_current_user_id),
    client: Client = Depends(get_user_client),
    idempotency_key: str | None = Depends(get_idempotency_key),
):
    \"\"\"Start async adapter training job. Returns immediately with job_id.

    v2: Trains the user's Linear Adapter from categorized transactions.
    The frozen MiniLM base model is never retrained.
    \"\"\"
    async def _execute():"""

    content = content.replace(upload_sig_target, upload_sig_replacement)
    content = content.replace(train_sig_target, train_sig_replacement)

    # Now we need to indent the bodies. We'll do this by finding the start and end of each block.
    # Upload block starts right after upload_sig_replacement till the start of `@router.get("/status/{job_id}")`
    # Train block starts right after train_sig_replacement to the end of the file.
    
    parts = content.split('@router.get("/status/{job_id}")')
    # part 0 contains upload body
    upload_body_match = parts[0].split('async def _execute():\n')
    if len(upload_body_match) > 1:
        body_lines = upload_body_match[1].splitlines()
        indented_body = "\n".join("    " + line if line.strip() else line for line in body_lines)
        indented_body += "\n    return await with_idempotency(idempotency_key, _execute)\n\n"
        parts[0] = upload_body_match[0] + 'async def _execute():\n' + indented_body
        
    content = '@router.get("/status/{job_id}")'.join(parts)
    
    parts = content.split('async def _execute():\n')
    if len(parts) > 2:
        train_body_lines = parts[2].splitlines()
        indented_train_body = "\n".join("    " + line if line.strip() else line for line in train_body_lines)
        indented_train_body += "\n    return await with_idempotency(idempotency_key, _execute)\n"
        
        parts[2] = indented_train_body
        content = 'async def _execute():\n'.join(parts)

    with open(filepath, 'w') as f:
        f.write(content)

process_file_training("apps/api/domains/training/router.py")
