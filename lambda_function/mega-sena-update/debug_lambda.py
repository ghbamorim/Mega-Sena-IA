# debug_lambda.py
import debugpy
from hello_world.app import lambda_handler

# Espera o VSCode conectar
debugpy.listen(("0.0.0.0", 5678))
print("Aguardando debugger no VSCode...")
debugpy.wait_for_client()

# Evento de teste
event = {}
context = None

result = lambda_handler(event, context)
print(result)
