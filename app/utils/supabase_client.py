import os
from dotenv import load_dotenv
from supabase import create_client

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL:
    raise ValueError("SUPABASE_URL is not set in environment")
if not SUPABASE_KEY:
    raise ValueError("SUPABASE_KEY is not set in environment")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
