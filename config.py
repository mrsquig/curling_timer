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