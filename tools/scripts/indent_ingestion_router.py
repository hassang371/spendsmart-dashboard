def process_file_ingestion(filepath):
    with open(filepath, "r") as f:
        content = f.read()

    # Add import
    import_stmt = "from apps.api.core.idempotency import get_idempotency_key, with_idempotency\n"
    if "get_idempotency_key" not in content:
        content = content.replace(
            "from supabase import Client\n",
            "from supabase import Client\n" + import_stmt,
        )

    import_sig_target = """async def import_file(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    password: str = Form(None),
    user_id: str = Depends(get_current_user_id),
    client: Client = Depends(get_user_client),
):
    \"\"\"v3 Import: insert-first, classify-later."""

    import_sig_replacement = """async def import_file(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    password: str = Form(None),
    user_id: str = Depends(get_current_user_id),
    client: Client = Depends(get_user_client),
    idempotency_key: str | None = Depends(get_idempotency_key),
):
    \"\"\"v3 Import: insert-first, classify-later.

    1. Parse file
    2. File-hash dedup (reject already-uploaded files)
    3. Build rows + fingerprints
    4. Insert ALL as Uncategorized via single RPC (ON CONFLICT handles dedup)
    5. Enqueue background classification
    6. Return immediately — categories appear via refreshAfterImport()
    \"\"\"
    async def _execute():"""

    # We also need to remove the docstring from the body so we don't duplicate it.
    # The original file has the docstring right after the signature.
    # We will replace the whole signature + docstring.

    full_target = """async def import_file(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    password: str = Form(None),
    user_id: str = Depends(get_current_user_id),
    client: Client = Depends(get_user_client),
):
    \"\"\"v3 Import: insert-first, classify-later.

    1. Parse file
    2. File-hash dedup (reject already-uploaded files)
    3. Build rows + fingerprints
    4. Insert ALL as Uncategorized via single RPC (ON CONFLICT handles dedup)
    5. Enqueue background classification
    6. Return immediately — categories appear via refreshAfterImport()
    \"\"\""""

    content = content.replace(full_target, import_sig_replacement)

    parts = content.split("async def _execute():\n")
    if len(parts) > 1:
        # The body is everything after `async def _execute():\n` until the end of the file, because `import_file` is the last function in router.py
        body_lines = parts[1].splitlines()
        indented_body = "\n".join("    " + line if line.strip() else line for line in body_lines)
        indented_body += "\n    return await with_idempotency(idempotency_key, _execute)\n"

        parts[1] = indented_body
        content = "async def _execute():\n".join(parts)

    with open(filepath, "w") as f:
        f.write(content)


process_file_ingestion("apps/api/domains/ingestion/router.py")
