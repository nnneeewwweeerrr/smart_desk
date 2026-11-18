
from services.state_manager import system_state

print(system_state.set_posture_command("calibrate"))
print(system_state.get_posture_command())
print(system_state.get_posture_command())

print(system_state.set_posture_command("reset"))
print(system_state.get_posture_command())

print(system_state.set_posture_command("wrong"))
