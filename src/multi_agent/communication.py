"""
多智能体通信系统
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable
import time
import uuid
from queue import Queue, Empty
import threading
import json


class MessageType(Enum):
    """消息类型"""
    TASK_REQUEST = "task_request"
    TASK_RESPONSE = "task_response"
    DATA_SHARE = "data_share"
    COORDINATION = "coordination"
    ERROR_REPORT = "error_report"
    STATUS_UPDATE = "status_update"
    COLLABORATION_REQUEST = "collaboration_request"
    RESULT_VALIDATION = "result_validation"


class MessagePriority(Enum):
    """消息优先级"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


@dataclass
class Message:
    """智能体间通信消息"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sender: str = ""
    receiver: str = ""
    message_type: MessageType = MessageType.TASK_REQUEST
    priority: MessagePriority = MessagePriority.NORMAL
    content: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    requires_response: bool = False
    response_timeout: float = 30.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "sender": self.sender,
            "receiver": self.receiver,
            "message_type": self.message_type.value,
            "priority": self.priority.value,
            "content": self.content,
            "timestamp": self.timestamp,
            "requires_response": self.requires_response,
            "response_timeout": self.response_timeout,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """从字典创建消息"""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            sender=data.get("sender", ""),
            receiver=data.get("receiver", ""),
            message_type=MessageType(data.get("message_type", "task_request")),
            priority=MessagePriority(data.get("priority", 2)),
            content=data.get("content", {}),
            timestamp=data.get("timestamp", time.time()),
            requires_response=data.get("requires_response", False),
            response_timeout=data.get("response_timeout", 30.0),
            metadata=data.get("metadata", {})
        )


class MessageBus:
    """消息总线 - 智能体间通信的中心枢纽"""
    
    def __init__(self):
        self.message_queues: Dict[str, Queue] = {}
        self.subscribers: Dict[MessageType, List[str]] = {}
        self.message_handlers: Dict[str, Callable] = {}
        self.message_history: List[Message] = []
        self.active_agents: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._running = False
        self._worker_thread = None
    
    def register_agent(self, agent_id: str, agent_info: Dict[str, Any] = None):
        """注册智能体"""
        with self._lock:
            if agent_id not in self.message_queues:
                self.message_queues[agent_id] = Queue()
                self.active_agents[agent_id] = agent_info or {}
                print(f"📝 智能体 {agent_id} 已注册到消息总线")
    
    def unregister_agent(self, agent_id: str):
        """注销智能体"""
        with self._lock:
            if agent_id in self.message_queues:
                del self.message_queues[agent_id]
                del self.active_agents[agent_id]
                # 清理订阅
                for msg_type in self.subscribers:
                    if agent_id in self.subscribers[msg_type]:
                        self.subscribers[msg_type].remove(agent_id)
                print(f"📝 智能体 {agent_id} 已从消息总线注销")
    
    def subscribe(self, agent_id: str, message_type: MessageType):
        """订阅消息类型"""
        with self._lock:
            if message_type not in self.subscribers:
                self.subscribers[message_type] = []
            if agent_id not in self.subscribers[message_type]:
                self.subscribers[message_type].append(agent_id)
                print(f"📡 智能体 {agent_id} 订阅了消息类型: {message_type.value}")
    
    def send_message(self, message: Message) -> bool:
        """发送消息"""
        try:
            with self._lock:
                # 记录消息历史
                self.message_history.append(message)
                
                # 如果是广播消息
                if message.receiver == "broadcast":
                    subscribers = self.subscribers.get(message.message_type, [])
                    for agent_id in subscribers:
                        if agent_id != message.sender and agent_id in self.message_queues:
                            self.message_queues[agent_id].put(message)
                    return True
                
                # 点对点消息
                if message.receiver in self.message_queues:
                    self.message_queues[message.receiver].put(message)
                    print(f"📤 消息已发送: {message.sender} → {message.receiver} ({message.message_type.value})")
                    return True
                else:
                    print(f"❌ 接收者 {message.receiver} 未注册")
                    return False
        
        except Exception as e:
            print(f"❌ 发送消息失败: {e}")
            return False
    
    def receive_message(self, agent_id: str, timeout: float = 1.0) -> Optional[Message]:
        """接收消息"""
        try:
            if agent_id in self.message_queues:
                return self.message_queues[agent_id].get(timeout=timeout)
        except Empty:
            return None
        except Exception as e:
            print(f"❌ 接收消息失败: {e}")
            return None
    
    def broadcast_message(self, sender: str, message_type: MessageType, content: Dict[str, Any]) -> bool:
        """广播消息"""
        message = Message(
            sender=sender,
            receiver="broadcast",
            message_type=message_type,
            content=content
        )
        return self.send_message(message)
    
    def get_active_agents(self) -> List[str]:
        """获取活跃智能体列表"""
        with self._lock:
            return list(self.active_agents.keys())
    
    def get_message_history(self, agent_id: str = None, message_type: MessageType = None) -> List[Message]:
        """获取消息历史"""
        history = self.message_history.copy()
        
        if agent_id:
            history = [msg for msg in history if msg.sender == agent_id or msg.receiver == agent_id]
        
        if message_type:
            history = [msg for msg in history if msg.message_type == message_type]
        
        return history
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取消息总线统计信息"""
        with self._lock:
            stats = {
                "total_agents": len(self.active_agents),
                "total_messages": len(self.message_history),
                "message_types": {},
                "agent_activity": {}
            }
            
            # 统计消息类型
            for msg in self.message_history:
                msg_type = msg.message_type.value
                stats["message_types"][msg_type] = stats["message_types"].get(msg_type, 0) + 1
            
            # 统计智能体活动
            for msg in self.message_history:
                sender = msg.sender
                stats["agent_activity"][sender] = stats["agent_activity"].get(sender, 0) + 1
            
            return stats
    
    def clear_history(self):
        """清空消息历史"""
        with self._lock:
            self.message_history.clear()
            print("🗑️ 消息历史已清空")


class CommunicationProtocol:
    """通信协议"""
    
    @staticmethod
    def create_task_request(sender: str, receiver: str, task_description: str, 
                          task_data: Dict[str, Any], priority: MessagePriority = MessagePriority.NORMAL) -> Message:
        """创建任务请求消息"""
        return Message(
            sender=sender,
            receiver=receiver,
            message_type=MessageType.TASK_REQUEST,
            priority=priority,
            content={
                "task_description": task_description,
                "task_data": task_data,
                "request_time": time.time()
            },
            requires_response=True
        )
    
    @staticmethod
    def create_task_response(sender: str, receiver: str, request_id: str, 
                           result: Dict[str, Any], success: bool = True) -> Message:
        """创建任务响应消息"""
        return Message(
            sender=sender,
            receiver=receiver,
            message_type=MessageType.TASK_RESPONSE,
            content={
                "request_id": request_id,
                "result": result,
                "success": success,
                "response_time": time.time()
            }
        )
    
    @staticmethod
    def create_data_share(sender: str, receiver: str, data: Dict[str, Any], 
                         data_type: str = "general") -> Message:
        """创建数据共享消息"""
        return Message(
            sender=sender,
            receiver=receiver,
            message_type=MessageType.DATA_SHARE,
            content={
                "data": data,
                "data_type": data_type,
                "share_time": time.time()
            }
        )
    
    @staticmethod
    def create_collaboration_request(sender: str, receiver: str, collaboration_type: str,
                                   details: Dict[str, Any]) -> Message:
        """创建协作请求消息"""
        return Message(
            sender=sender,
            receiver=receiver,
            message_type=MessageType.COLLABORATION_REQUEST,
            priority=MessagePriority.HIGH,
            content={
                "collaboration_type": collaboration_type,
                "details": details,
                "request_time": time.time()
            },
            requires_response=True
        )
    
    @staticmethod
    def create_status_update(sender: str, status: str, details: Dict[str, Any] = None) -> Message:
        """创建状态更新消息"""
        return Message(
            sender=sender,
            receiver="broadcast",
            message_type=MessageType.STATUS_UPDATE,
            content={
                "status": status,
                "details": details or {},
                "update_time": time.time()
            }
        )