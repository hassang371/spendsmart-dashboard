import os
from supabase import create_client, Client

url = "https://nbtowufbthavewruaicc.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5idG93dWZidGhhdmV3cnVhaWNjIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MDQzNTUwNSwiZXhwIjoyMDg2MDExNTA1fQ.MiTWR2XIYDQ5GT5aNsonbY0_QByFL5Fiieq30p4Ow-g"

def cleanup_global_models():
    print("Initializing Supabase Auth client...")
    supabase: Client = create_client(url, key)
    
    print("Checking 'models' bucket for 'global' folder...")
    try:
        res = supabase.storage.from_("models").list("global")
        print("Found items:", res)
        
        files_to_remove = []
        for item in res:
            if item['name'] != '.emptyFolderPlaceholder':
                files_to_remove.append(f"global/{item['name']}")
                
        if files_to_remove:
            print(f"Removing files: {files_to_remove}")
            remove_res = supabase.storage.from_("models").remove(files_to_remove)
            print(f"Removal response: {remove_res}")
        else:
            print("No files to remove in global/")
            
    except Exception as e:
        print(f"Error accessing storage: {e}")

if __name__ == "__main__":
    cleanup_global_models()
