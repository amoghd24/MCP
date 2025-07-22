"""
Rate limiting utilities for MCP server
"""

import time
from typing import Dict, Optional
from functools import wraps
import asyncio


class TokenBucket:
    """Token bucket implementation for rate limiting"""
    
    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.tokens = capacity
        self.refill_rate = refill_rate
        self.last_refill = time.time()
    
    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens from the bucket"""
        self._refill()
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False
    
    def _refill(self):
        """Refill tokens based on time elapsed"""
        now = time.time()
        elapsed = now - self.last_refill
        tokens_to_add = elapsed * self.refill_rate
        
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now


class RateLimiter:
    """Rate limiter for API calls"""
    
    def __init__(self, requests_per_minute: int = 60, burst: int = 10):
        self.buckets: Dict[str, TokenBucket] = {}
        self.requests_per_minute = requests_per_minute
        self.burst = burst
        # Calculate refill rate (tokens per second)
        self.refill_rate = requests_per_minute / 60.0
    
    def get_bucket(self, key: str) -> TokenBucket:
        """Get or create a token bucket for a key"""
        if key not in self.buckets:
            self.buckets[key] = TokenBucket(
                capacity=self.burst,
                refill_rate=self.refill_rate
            )
        return self.buckets[key]
    
    def check_rate_limit(self, key: str, tokens: int = 1) -> bool:
        """Check if request is allowed under rate limit"""
        bucket = self.get_bucket(key)
        return bucket.consume(tokens)
    
    def reset(self, key: str):
        """Reset rate limit for a key"""
        if key in self.buckets:
            del self.buckets[key]


# Global rate limiter instance
rate_limiter = RateLimiter()


def rate_limited(key_func=None, tokens: int = 1):
    """Decorator for rate limiting function calls"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Determine rate limit key
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                # Default to function name
                key = func.__name__
            
            # Check rate limit
            if not rate_limiter.check_rate_limit(key, tokens):
                raise Exception(f"Rate limit exceeded for {key}")
            
            # Call function
            return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Determine rate limit key
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                # Default to function name
                key = func.__name__
            
            # Check rate limit
            if not rate_limiter.check_rate_limit(key, tokens):
                raise Exception(f"Rate limit exceeded for {key}")
            
            # Call function
            return func(*args, **kwargs)
        
        # Return appropriate wrapper
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


class APIRateLimiter:
    """Specific rate limiter for external API calls"""
    
    def __init__(self):
        self.limits = {
            "notion": RateLimiter(requests_per_minute=180, burst=20),
            "slack": RateLimiter(requests_per_minute=60, burst=10),
            "github": RateLimiter(requests_per_minute=5000, burst=100),  # GitHub has higher limits
            "amplitude": RateLimiter(requests_per_minute=360, burst=5),  # 360 queries/hour, 5 concurrent
        }
        # Amplitude-specific cost tracking
        self.amplitude_costs: Dict[str, Dict[str, float]] = {}  # user_id -> {timestamp -> cost}
        self.amplitude_concurrent: Dict[str, int] = {}  # user_id -> active_requests
    
    def check_api_limit(self, api: str, user_id: str) -> bool:
        """Check rate limit for specific API and user"""
        if api in self.limits:
            key = f"{api}:{user_id}"
            return self.limits[api].check_rate_limit(key)
        return True  # No limit defined
    
    def wait_if_limited(self, api: str, user_id: str) -> Optional[float]:
        """Return wait time if rate limited, None if not limited"""
        if api in self.limits:
            key = f"{api}:{user_id}"
            bucket = self.limits[api].get_bucket(key)
            if bucket.tokens < 1:
                # Calculate wait time until next token
                wait_time = (1 - bucket.tokens) / bucket.refill_rate
                return wait_time
        return None
    
    def calculate_amplitude_cost(self, days: int, conditions: int, query_type_cost: int) -> int:
        """Calculate Amplitude API cost: (# of days) * (# of conditions) * (query type cost)"""
        return days * conditions * query_type_cost
    
    def check_amplitude_limits(self, user_id: str, cost: int) -> bool:
        """Check Amplitude-specific limits: cost per hour and concurrent requests"""
        now = time.time()
        hour_ago = now - 3600  # 1 hour in seconds
        
        # Initialize user tracking if needed
        if user_id not in self.amplitude_costs:
            self.amplitude_costs[user_id] = {}
        if user_id not in self.amplitude_concurrent:
            self.amplitude_concurrent[user_id] = 0
        
        # Clean up old cost entries (older than 1 hour)
        user_costs = self.amplitude_costs[user_id]
        old_timestamps = [ts for ts in user_costs.keys() if float(ts) < hour_ago]
        for ts in old_timestamps:
            del user_costs[ts]
        
        # Calculate current hourly cost
        current_hourly_cost = sum(user_costs.values())
        
        # Check cost limit (1000 cost per 5 minutes = 12000 per hour)
        if current_hourly_cost + cost > 12000:
            return False
        
        # Check concurrent requests limit (5 concurrent)
        if self.amplitude_concurrent[user_id] >= 5:
            return False
        
        return True
    
    def start_amplitude_request(self, user_id: str, cost: int) -> bool:
        """Start tracking an Amplitude request"""
        if not self.check_amplitude_limits(user_id, cost):
            return False
        
        now = time.time()
        
        # Record the cost
        self.amplitude_costs[user_id][str(now)] = cost
        
        # Increment concurrent request counter
        if user_id not in self.amplitude_concurrent:
            self.amplitude_concurrent[user_id] = 0
        self.amplitude_concurrent[user_id] += 1
        
        return True
    
    def end_amplitude_request(self, user_id: str):
        """End tracking an Amplitude request"""
        if user_id in self.amplitude_concurrent and self.amplitude_concurrent[user_id] > 0:
            self.amplitude_concurrent[user_id] -= 1


# Global API rate limiter
api_rate_limiter = APIRateLimiter() 