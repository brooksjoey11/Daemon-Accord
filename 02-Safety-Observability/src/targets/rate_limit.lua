local domain_key = KEYS[1]
local ip_key = KEYS[2]
local concurrent_key = KEYS[3]
local config_key = KEYS[4]

local domain_limit = tonumber(ARGV[1])
local ip_limit = tonumber(ARGV[2])
local concurrent_limit = tonumber(ARGV[3])
local current_time = tonumber(ARGV[4])
local minute_window = tonumber(ARGV[5])
local hour_window = tonumber(ARGV[6])
local concurrent_timeout = tonumber(ARGV[7])

-- Initialize counters if they don't exist
redis.call('SETNX', domain_key, 0)
redis.call('SETNX', ip_key, 0)
redis.call('SETNX', concurrent_key, 0)

-- Get current counts
local domain_count = tonumber(redis.call('GET', domain_key))
local ip_count = tonumber(redis.call('GET', ip_key))
local concurrent_count = tonumber(redis.call('GET', concurrent_key))

-- Check if any limit is exceeded
local allowed = 1
local remaining = math.max(domain_limit - domain_count, 0)
local reset_after = minute_window

if domain_count >= domain_limit then
    allowed = 0
    reset_after = redis.call('PTTL', domain_key)
    if reset_after < 0 then
        reset_after = minute_window
    end
elseif ip_count >= ip_limit then
    allowed = 0
    reset_after = redis.call('PTTL', ip_key)
    if reset_after < 0 then
        reset_after = hour_window
    end
elseif concurrent_count >= concurrent_limit then
    allowed = 0
    reset_after = redis.call('PTTL', concurrent_key)
    if reset_after < 0 then
        reset_after = concurrent_timeout
    end
else
    -- All limits OK, increment counters
    if domain_count == 0 then
        redis.call('PSETEX', domain_key, minute_window * 1000, 1)
    else
        redis.call('INCR', domain_key)
    end
    
    if ip_count == 0 then
        redis.call('PSETEX', ip_key, hour_window * 1000, 1)
    else
        redis.call('INCR', ip_key)
    end
    
    if concurrent_count == 0 then
        redis.call('PSETEX', concurrent_key, concurrent_timeout * 1000, 1)
    else
        redis.call('INCR', concurrent_key)
    end
    
    remaining = domain_limit - domain_count - 1
    reset_after = minute_window
end

return {allowed, remaining, reset_after}
