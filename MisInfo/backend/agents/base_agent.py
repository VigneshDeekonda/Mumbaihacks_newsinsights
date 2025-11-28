import asyncio
import json
import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AgentStatus(Enum):
    """Enumeration of possible agent statuses"""
    IDLE = "idle"
    PROCESSING = "processing"
    WAITING = "waiting"
    ERROR = "error"
    COMPLETED = "completed"


class TaskPriority(Enum):
    """Enumeration of task priorities"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class AgentTask:
    """Represents a task for an agent to process"""
    task_id: str
    agent_type: str
    priority: TaskPriority
    payload: Dict[str, Any]
    created_at: datetime
    dependencies: List[str] = None
    status: AgentStatus = AgentStatus.IDLE
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


@dataclass
class AgentMessage:
    """Represents a message between agents"""
    sender: str
    recipient: str
    message_type: str
    content: Dict[str, Any]
    timestamp: datetime
    priority: TaskPriority = TaskPriority.NORMAL


class BaseAgent(ABC):
    """Base class for all agents in the system"""
    
    def __init__(self, agent_id: str, agent_name: str):
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.status = AgentStatus.IDLE
        self.current_task = None
        self.message_queue = asyncio.Queue()
        self.task_history = []
        
    @abstractmethod
    async def process_task(self, task: AgentTask) -> Dict[str, Any]:
        """
        Process a task and return results.
        
        Args:
            task (AgentTask): The task to process
            
        Returns:
            Dict[str, Any]: The result of processing the task
        """
        pass
    
    async def send_message(self, message: AgentMessage, coordinator):
        """
        Send a message to another agent via the coordinator.
        
        Args:
            message (AgentMessage): The message to send
            coordinator: The coordinator to route the message through
        """
        await coordinator.route_message(message)
    
    async def receive_message(self) -> AgentMessage:
        """Receive a message from the message queue"""
        return await self.message_queue.get()
    
    def update_status(self, status: AgentStatus):
        """
        Update the agent's status.
        
        Args:
            status (AgentStatus): The new status
        """
        self.status = status
        logger.info(f"[{self.agent_name}] Status updated to {status.value}")


class AgentCoordinator:
    """Central coordinator for agent communication and task management"""
    
    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {}
        self.task_queue = asyncio.PriorityQueue()
        self.message_broker = {}
        self.task_counter = 0
        
    def register_agent(self, agent: BaseAgent):
        """
        Register an agent with the coordinator.
        
        Args:
            agent (BaseAgent): The agent to register
        """
        self.agents[agent.agent_id] = agent
        logger.info(f"Registered agent: {agent.agent_name} ({agent.agent_id})")
    
    async def submit_task(self, task: AgentTask):
        """
        Submit a task to the queue.
        
        Args:
            task (AgentTask): The task to submit
        """
        # Priority queue uses lowest number first, so we negate the priority
        priority = -task.priority.value
        await self.task_queue.put((priority, task))
        logger.info(f"Task {task.task_id} submitted for {task.agent_type}")
    
    async def route_message(self, message: AgentMessage):
        """
        Route a message to the appropriate agent.
        
        Args:
            message (AgentMessage): The message to route
        """
        if message.recipient in self.agents:
            await self.agents[message.recipient].message_queue.put(message)
            logger.info(f"Message routed from {message.sender} to {message.recipient}")
        else:
            logger.error(f"Recipient {message.recipient} not found")
    
    async def run_coordinator(self):
        """Main coordinator loop to process tasks"""
        logger.info("Coordinator loop started")
        while True:
            try:
                # Get the highest priority task
                priority, task = await self.task_queue.get()
                
                # Find the appropriate agent
                agent = None
                for agent_id, registered_agent in self.agents.items():
                    if registered_agent.agent_id == task.agent_type or registered_agent.agent_name == task.agent_type:
                        agent = registered_agent
                        break
                
                if agent:
                    try:
                        agent.update_status(AgentStatus.PROCESSING)
                        result = await agent.process_task(task)
                        task.result = result
                        task.status = AgentStatus.COMPLETED
                        agent.update_status(AgentStatus.IDLE)
                        logger.info(f"Task {task.task_id} completed successfully")
                    except Exception as e:
                        task.status = AgentStatus.ERROR
                        task.error_message = str(e)
                        agent.update_status(AgentStatus.ERROR)
                        logger.error(f"Task {task.task_id} failed: {e}")
                else:
                    logger.error(f"No agent found for task type: {task.agent_type}")
                
                self.task_queue.task_done()
                
            except Exception as e:
                logger.error(f"Error in coordinator loop: {e}")
                await asyncio.sleep(1)