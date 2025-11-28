"""
Project Aegis - Herald Agent
Generates public alerts based on investigation results
"""

import logging
from typing import Dict, Any
import json

from .base_agent import BaseAgent, AgentTask, AgentStatus, TaskPriority
from backend.prompts import HERALD_PROTOCOL

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HeraldAgent(BaseAgent):
    """Agent responsible for generating public alerts and communications"""
    
    def __init__(self, agent_id: str = "herald_agent_001"):
        super().__init__(agent_id, "HeraldAgent")
    
    def generate_alert(self, investigator_report: Dict[str, Any]) -> str:
        """
        Generate a public alert based on the investigator's report.
        
        Args:
            investigator_report (Dict[str, Any]): The report from the investigator agent
            
        Returns:
            str: Formatted public alert string
        """
        logger.info(f"[{self.agent_name}] Generating public alert")
        logger.debug(f"[{self.agent_name}] Report: {json.dumps(investigator_report, indent=2)}")
        
        verdict = investigator_report.get("verdict", "Misleading")
        confidence = investigator_report.get("confidence", 0.5)
        reasoning = investigator_report.get("reasoning", "No reasoning provided")
        
        # Select appropriate emoji based on verdict
        if verdict == "True":
            emoji = "🟢"
        elif verdict == "False":
            emoji = "🔴"
        else:  # Misleading
            emoji = "🟡"
        
        # Generate public alert message
        if verdict == "True":
            message = f"This information has been verified as accurate. {reasoning} Our confidence level is {confidence*100:.0f}%."
        elif verdict == "False":
            message = f"This information has been confirmed as false. {reasoning} Our confidence level is {confidence*100:.0f}%."
        else:  # Misleading
            message = f"This information may be misleading. {reasoning} Our confidence level is {confidence*100:.0f}%."
        
        alert = f"{emoji} {message}"
        logger.info(f"[{self.agent_name}] Alert generated: {alert[:50]}...")
        return alert
    
    async def process_task(self, task: AgentTask) -> Dict[str, Any]:
        """
        Process a task to generate a public alert.
        
        Args:
            task (AgentTask): The task containing the investigator report
            
        Returns:
            Dict[str, Any]: The generated public alert
        """
        logger.info(f"[{self.agent_name}] Processing alert generation task {task.task_id}")
        
        # Extract investigator report from payload
        investigator_report_json = task.payload.get("investigator_report_json", "{}")
        
        try:
            investigator_report = json.loads(investigator_report_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in investigator_report_json: {e}")
        
        # Generate the public alert
        alert_message = self.generate_alert(investigator_report)
        
        return {
            "investigator_report": investigator_report,
            "public_alert": alert_message,
            "alert_timestamp": task.created_at.isoformat()
        }


# Example usage
if __name__ == "__main__":
    import asyncio
    from datetime import datetime
    
    async def main():
        # Create the herald agent
        herald_agent = HeraldAgent()
        
        # Create a sample investigator report
        sample_report = {
            "verdict": "False",
            "confidence": 0.95,
            "reasoning": "Multiple credible sources contradict this claim, and scientific consensus confirms the opposite."
        }
        
        # Create a sample task
        task = AgentTask(
            task_id="alert_task_001",
            agent_type="HeraldAgent",
            priority=TaskPriority.NORMAL,
            payload={
                "investigator_report_json": json.dumps(sample_report)
            },
            created_at=datetime.now()
        )
        
        # Process the task
        result = await herald_agent.process_task(task)
        print("Herald Agent Result:")
        print(json.dumps(result, indent=2))
    
    # Run the example
    asyncio.run(main())