from abc import ABC, abstractmethod

class BaseModel(ABC):
    
    @abstractmethod
    def get_model(self):
        pass