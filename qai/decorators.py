from functools import wraps
import asyncio


def nickserv_identified(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            self, mask = args[0], args[1]
            if not (await self._Plugin__is_nick_serv_identified(mask.nick)):
                return
        except Exception:
            pass
        return func(*args, **kwargs)

    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        try:
            self, mask = args[0], args[1]
            if not (await self._Plugin__is_nick_serv_identified(mask.nick)):
                return
        except Exception:
            pass
        return await func(*args, **kwargs)

    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return wrapper


def channel_only(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            self, target = args[0], args[2]
            if not self._is_a_channel(target):
                return 'You can only use this command in channels.'
        except Exception:
            pass
        return func(*args, **kwargs)

    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        try:
            self, target = args[0], args[2]
            if not self._is_a_channel(target):
                return 'You can only use this command in channels.'
        except Exception:
            pass
        return await func(*args, **kwargs)

    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return wrapper
