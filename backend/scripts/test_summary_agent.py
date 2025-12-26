
import asyncio
import sys
from pathlib import Path
import os
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))

# Load env vars before import just in case
load_dotenv()

from src.infrastructure.agents.summary_agent import summary_agent

async def test_summary():
    print(f"Summary agent type: {type(summary_agent)}")
    
    report_text = "Patient has high cholesterol. HDL 40, LDL 160. Recommend diet changes."
    
    try:
        print("Calling summary_agent...")
        result = await summary_agent(report_text)
        print(f"Result type: {type(result)}")
        print(f"Result: {result}")
        print("SUCCESS")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_summary())
