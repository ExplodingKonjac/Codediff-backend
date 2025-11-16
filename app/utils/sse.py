import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def sse_response(event_type, data, event_id=None):
    """
    格式化 SSE (Server-Sent Events) 响应
    
    Args:
        event_type: 事件类型 (如 'test_result', 'error', 'completed')
        data: 事件数据 (字典)
        event_id: 事件ID (可选)
    
    Returns:
        格式化的 SSE 字符串
    """
    # 添加时间戳
    data['timestamp'] = datetime.utcnow().isoformat()
    
    response = []
    
    if event_id:
        response.append(f'id: {event_id}')
    
    response.append(f'event: {event_type}')
    response.append(f'data: {json.dumps(data, ensure_ascii=False)}')
    response.append('')  # 空行表示事件结束
    
    return '\n'.join(response)

def sse_error(message, details=None, code=500):
    """生成错误 SSE 事件"""
    data = {
        'error': True,
        'message': message,
        'code': code
    }
    if details:
        data['details'] = details
    
    return sse_response('error', data)

def sse_completed(total=None, success=None, fail=None, reason=None):
    """生成完成 SSE 事件"""
    data = {
        'status': 'completed'
    }
    if total is not None:
        data['total'] = total
    if success is not None:
        data['success'] = success
    if fail is not None:
        data['fail'] = fail
    if reason:
        data['reason'] = reason
    
    return sse_response('completed', data)

def sse_heartbeat():
    """生成心跳事件 (保持连接活跃)"""
    return sse_response('heartbeat', {'message': 'Connection alive'})

class SSEManager:
    """SSE 连接管理器"""
    
    def __init__(self):
        self.connections = {}
        self.logger = logging.getLogger('sse.manager')
    
    def register_connection(self, session_id, client_id, stream):
        """注册新连接"""
        if session_id not in self.connections:
            self.connections[session_id] = {}
        
        self.connections[session_id][client_id] = {
            'stream': stream,
            'created_at': datetime.utcnow(),
            'last_heartbeat': datetime.utcnow()
        }
        
        self.logger.info(f'Registered SSE connection: session={session_id}, client={client_id}')
        return True
    
    def unregister_connection(self, session_id, client_id):
        """注销连接"""
        if session_id in self.connections and client_id in self.connections[session_id]:
            del self.connections[session_id][client_id]
            if not self.connections[session_id]:
                del self.connections[session_id]
            
            self.logger.info(f'Unregistered SSE connection: session={session_id}, client={client_id}')
            return True
        return False
    
    def broadcast_event(self, session_id, event_type, data):
        """向会话的所有客户端广播事件"""
        if session_id not in self.connections:
            return 0
        
        success_count = 0
        failed_clients = []
        
        for client_id, conn in list(self.connections[session_id].items()):
            try:
                event = sse_response(event_type, data, event_id=f"{session_id}-{client_id}-{int(datetime.utcnow().timestamp())}")
                conn['stream'].write(event)
                conn['stream'].flush()
                conn['last_heartbeat'] = datetime.utcnow()
                success_count += 1
            except Exception as e:
                self.logger.warning(f'Failed to send event to client {client_id}: {str(e)}')
                failed_clients.append(client_id)
        
        # 清理失败的连接
        for client_id in failed_clients:
            self.unregister_connection(session_id, client_id)
        
        return success_count
    
    def send_heartbeat(self):
        """发送心跳到所有活跃连接"""
        now = datetime.utcnow()
        for session_id in list(self.connections.keys()):
            for client_id, conn in list(self.connections[session_id].items()):
                # 检查连接是否超时
                if (now - conn['last_heartbeat']).total_seconds() > 300:  # 5分钟
                    self.logger.info(f'Closing stale SSE connection: session={session_id}, client={client_id}')
                    self.unregister_connection(session_id, client_id)
                    continue
                
                # 每30秒发送一次心跳
                if (now - conn['last_heartbeat']).total_seconds() > 30:
                    try:
                        event = sse_heartbeat()
                        conn['stream'].write(event)
                        conn['stream'].flush()
                        conn['last_heartbeat'] = now
                    except Exception as e:
                        self.logger.warning(f'Failed to send heartbeat to client {client_id}: {str(e)}')
                        self.unregister_connection(session_id, client_id)

# 全局 SSE 管理器实例
sse_manager = SSEManager()
