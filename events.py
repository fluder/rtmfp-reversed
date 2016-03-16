class EventDriven(object):
    def __init__(self):
        self._event_listeners = {}

    def connect(self, event, cb):
        listeners = self._event_listeners.get(event, set())
        listeners.add(cb)

        self._event_listeners[event] = listeners

    def disconnect(self, event, cb):
        listeners = self._event_listeners.get(event, set())
        listeners.remove(cb)

        self._event_listeners[event] = listeners

    def emit(self, event, *args, **kwargs):
        listeners = self._event_listeners.get(event, set())

        for listener in listeners:
            listener(self, *args, **kwargs)