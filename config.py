class ConfigValue(dict):
  def __init__(self, value, type_fun=str):
    self.type_fun = type_fun
    self._value = type_fun(value)
    dict.__init__(self, value=self._value)

  @property
  def value(self):
    return self._value

  @value.setter
  def value(self, value):
    self._value = self.type_fun(value)
    self["value"] = self._value

  def __repr__(self):
    return str(self.value)

# Helper function for converting values to an int before the call to bool()
# This is used for handling values that begin as strings but must be Booleans
bool_type = lambda x: bool(int(x))    