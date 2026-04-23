import asyncio

class MockPool:
    def __init__(self):
        self._closed = True
        self._opened = False
        
    async def open(self):
        if not self._closed:
            return
        if self._closed and self._opened:
            raise Exception("pool has already been opened/closed")
        self._closed = False
        self._opened = True

    async def wait(self):
        raise TimeoutError("PoolTimeout")
        
    async def close(self):
        self._closed = True

class Client:
    def __init__(self):
        self.pool = MockPool()
        self._pool_opened = False
        self._pool_lock = asyncio.Lock()
        
    async def _ensure_pool(self):
        async with self._pool_lock:
            # check if pool is dead
            if self.pool is not None and self.pool._closed and self.pool._opened:
                self.pool = MockPool()
                self._pool_opened = False
                
            if not self._pool_opened:
                try:
                    await self.pool.open()
                    await self.pool.wait()
                    self._pool_opened = True
                except Exception as e:
                    print(f"Error during pool initialization: {e}")
                    # Simulate the pool worker closing the pool on fatal error
                    await self.pool.close()
                    raise

async def main():
    c = Client()
    try:
        await c._ensure_pool()
    except Exception:
        pass
    print(f"Pool closed: {c.pool._closed}, opened: {c.pool._opened}")
    try:
        await c._ensure_pool()
    except Exception as e:
        print(f"Second call exception: {e}")
        
asyncio.run(main())
