-- Token bucket rate limiter Lua script for Redis
-- Keys: [1] = bucket key
-- Args: [1] = current timestamp (seconds with decimal)
--       [2] = tokens per interval
--       [3] = interval seconds
--       [4] = tokens requested
--       [5] = max tokens capacity

local key = KEYS[1]
local now = tonumber(ARGV[1])
local tokens_per_interval = tonumber(ARGV[2])
local interval_seconds = tonumber(ARGV[3])
local requested = tonumber(ARGV[4])
local max_tokens = tonumber(ARGV[5])

-- Get current bucket state
local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')

local current_tokens = 0
local last_refill = now

if bucket[1] then
    current_tokens = tonumber(bucket[1])
end

if bucket[2] then
    last_refill = tonumber(bucket[2])
end

-- Calculate tokens to add based on time passed
local time_passed = now - last_refill
local intervals_passed = math.floor(time_passed / interval_seconds)
local tokens_to_add = intervals_passed * tokens_per_interval

-- Refill tokens if needed
if tokens_to_add > 0 then
    current_tokens = math.min(current_tokens + tokens_to_add, max_tokens)
    last_refill = last_refill + (intervals_passed * interval_seconds)
end

-- Check if we have enough tokens
if current_tokens >= requested then
    -- Consume tokens
    current_tokens = current_tokens - requested
    
    -- Update bucket
    redis.call('HMSET', key, 'tokens', current_tokens, 'last_refill', last_refill)
    redis.call('EXPIRE', key, math.ceil(interval_seconds * 2))
    
    -- Return success, remaining tokens, and new last refill time
    return {1, current_tokens, last_refill}
else
    -- Calculate wait time until enough tokens are available
    local tokens_needed = requested - current_tokens
    local intervals_needed = math.ceil(tokens_needed / tokens_per_interval)
    local wait_seconds = (intervals_needed * interval_seconds) - (now - last_refill)
    
    -- Ensure wait_seconds is not negative
    if wait_seconds < 0 then
        wait_seconds = 0
    end
    
    -- Update bucket (even though we're not consuming)
    redis.call('HMSET', key, 'tokens', current_tokens, 'last_refill', last_refill)
    redis.call('EXPIRE', key, math.ceil(interval_seconds * 2))
    
    -- Return failure, current tokens, and wait time
    return {0, current_tokens, wait_seconds}
end
