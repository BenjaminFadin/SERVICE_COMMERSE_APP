import os
from dotenv import dotenv_values

config = dotenv_values(".env")

print(config.get('SECRET_KEY'))

