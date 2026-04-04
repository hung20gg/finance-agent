from pydantic import BaseModel, Field, ConfigDict

import os
import sys 
import random
import string

current_dir = os.path.dirname(os.path.abspath(__file__))


def random_string(length=10):
    """
    Generate a random string of fixed length.
    
    :param length: Length of the random string.
    :return: Random string.
    """
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


class EnvConfig(BaseModel):
    """
    Configuration for the environment.
    """
    name: str = Field(default='Environment', description="Purpose of the environment")
    module_name: str = 'env'
    cache_folder: str = Field(default=os.path.join(current_dir, '..', '..', 'temp', 'env'), description="Folder to cache environment files")
    
    def __init__(self, **data):
        super().__init__(**data)
        if not os.path.exists(self.cache_folder):
            os.makedirs(self.cache_folder)
            os.makedirs(os.path.join(self.cache_folder, 'images'), exist_ok=True)
            os.makedirs(os.path.join(self.cache_folder, 'code'), exist_ok=True)
    

class Env(BaseModel):
    """
    Represents an environment that can execute actions based on the provided configuration.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    config: EnvConfig

    def step(self, action: str, run_name: str = '', tag: str = '') -> str:
        """
        Perform an action in the environment.

        :param action: The action to perform.
        :return: Result of the action.
        """
        raise NotImplementedError("The step method must be implemented in subclasses.")


