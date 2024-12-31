import consul
import socket
import uuid
from config import settings
import logging

logger = logging.getLogger(__name__)

class ServiceDiscovery:
    def __init__(self):
        self.consul_client = consul.Consul(
            host=settings.CONSUL_HOST,
            port=settings.CONSUL_PORT
        )
        self.service_id = str(uuid.uuid4())
        self.service_name = settings.APP_NAME
        self.host = socket.gethostname()
        self.port = settings.APP_PORT
    
    def register(self):
        """Servisi Consul'a kaydet"""
        try:
            self.consul_client.agent.service.register(
                name=self.service_name,
                service_id=self.service_id,
                address=self.host,
                port=self.port,
                tags=['api', 'video-subtitler'],
                check={
                    'http': f'http://{self.host}:{self.port}/health',
                    'interval': '10s',
                    'timeout': '5s'
                }
            )
            logger.info(f"Service registered: {self.service_name} ({self.service_id})")
        except Exception as e:
            logger.error(f"Service registration failed: {str(e)}")
    
    def deregister(self):
        """Servisi Consul'dan kaldır"""
        try:
            self.consul_client.agent.service.deregister(self.service_id)
            logger.info(f"Service deregistered: {self.service_name} ({self.service_id})")
        except Exception as e:
            logger.error(f"Service deregistration failed: {str(e)}")
    
    def get_service(self, service_name: str) -> list:
        """Belirli bir servisin tüm instance'larını bul"""
        try:
            _, services = self.consul_client.health.service(
                service_name,
                passing=True
            )
            return [
                {
                    'id': service['Service']['ID'],
                    'address': service['Service']['Address'],
                    'port': service['Service']['Port']
                }
                for service in services
            ]
        except Exception as e:
            logger.error(f"Service discovery failed: {str(e)}")
            return []
    
    def watch_service(self, service_name: str, callback):
        """Servis değişikliklerini izle"""
        index = None
        while True:
            try:
                index, services = self.consul_client.health.service(
                    service_name,
                    index=index,
                    passing=True
                )
                callback(services)
            except Exception as e:
                logger.error(f"Service watch failed: {str(e)}")
                continue

# Singleton instance
service_discovery = ServiceDiscovery() 