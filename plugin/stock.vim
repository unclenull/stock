" rest_dates
" http://tools.2345.com/rili.htm
" formateJxData()


hi stk_up guifg='#5d6b00'
hi stk_up_hl guifg='#cb4b16'
hi stk_down guifg='#1d7069'
hi stk_down_hl guifg='#268bdc'
hi stk_even guifg='#586e6b'

let s:VAL_PLACEHOLDER = '-'
let s:stk_sep1 = '/'
let s:stk_sep2 = '|'

let s:stk_folder = $HOME . '/.stock'
if !isdirectory(s:stk_folder)
  call mkdir(s:stk_folder)
  call mkdir(s:stk_folder . '/cfg')
endif

let s:stk_config_path = s:stk_folder . '/cfg/stock.cfg.json'
let g:stk_data_path = s:stk_folder. '/stock.dat.json'
let s:stk_data_lock_path = s:stk_folder . '/stock.dat.lock'
let s:stk_runner_pid_path = s:stk_folder . '/stock.runner.pid'
let s:stk_runner_path = expand('<sfile>:p:h') . "/stock_runner.py"
let s:stk_config = {}
let s:stk_delay = 0
let g:stk_last_read_time = 0
let s:stk_cfg_ts = 0
let s:stk_timer = 0
let s:stk_retry = 0
let g:stk_output = ''

function! s:Log(msg)
  echom "[STOCK-". strftime("%m/%d %H:%M:%S") . '] ' . a:msg
endfunction

function! s:LogErr(msg)
  echohl WarningMsg
  echom "[STOCK-". strftime("%m/%d %H:%M:%S") . ']ERROR: ' . a:msg
  echohl None
endfunction

function! s:IsProcessRunning(pid)
  let l:running = 0

  python3 << EOF
import psutil
import vim

pid = int(vim.eval('a:pid'))
if pid > 0:
    try:
        ps = psutil.Process(pid)
        if ps.is_running() and ps.name() == 'python.exe' and ps.cmdline()[1].endswith("stock_runner.py"):
            vim.command('let l:running = 1')
        else:
            vim.command('let l:running = 0')
    except psutil.NoSuchProcess:
        pass
EOF
  return l:running
endfunction

function! s:CheckRunner(silent)
  if filereadable(s:stk_runner_pid_path)
    if getfsize(s:stk_runner_pid_path) > 0
      let l:pid = readfile(s:stk_runner_pid_path)[0]
      "echom 'pid: ' . l:pid
      if s:IsProcessRunning(l:pid)
        if !a:silent
          call s:Log("Runner already running " . l:pid)
        endif
        return l:pid
      else
        call s:Log("Stopped runner: " . l:pid)
      endif
    else
      if 1 || !a:silent
        call s:Log("Runner being started by another Vim")
      endif
      return 1
    endif
  endif

  return 0
endfunction

lua << EOF
local file_handle
function OpenDataFile()
    file_handle = io.open(vim.g.stk_data_path, 'r')
    if file_handle then
        file_handle:setvbuf("full", 4096)  -- Set buffer size for efficiency
        vim.api.nvim_command('call s:Log("Opened data file")')
    else
        vim.api.nvim_command('call s:LogErr("Failed opening data file")')
    end
end

-- Function to read the whole content of the file

function ReadDataInner()
    if not file_handle then
        OpenDataFile()
    end

    if file_handle then
        file_handle:seek("set")
        data = file_handle:read("*all")
        -- print(data)
        return data
    else
        vim.api.nvim_command('call s:LogErr("File handle not available")')
        return ""
    end
end

function CloseDataInner()
    if file_handle then
        file_handle:close()
        file_handle = nil
    end
end

function GetMidnight()
  -- Get the current time
  local now = os.time()

  -- Get the current date components
  local date_table = os.date("*t", now)

  -- Set the time components to midnight
  date_table.hour = 0
  date_table.min = 0
  date_table.sec = 0

  -- Get the Unix timestamp for the start of the day
  -- print(vim.inspect(date_table))
  return os.time(date_table)
end

function KillPid(pid)
  print("Killing runner: " .. pid)
  vim.loop.kill(pid, 9, on_exit)
  if ok then
  else
    print({{"Failed to invoke 'pcall', Lua error: "..err, "ErrorMsg"}}, true, {})
  end
end

EOF

function! s:CreateText(txt, hl)
  return "%#" . a:hl . '#' . a:txt
endfunction

function! s:ReadData()
  let l:content = luaeval('ReadDataInner()')
  "call s:Log('data content: ' . l:content)
  let g:stk_last_read_time = localtime()
  if len(l:content) > 0
    return json_decode(l:content)
  else
    return {}
  endif
endfunction

function! s:ReadConfig()
  "echom 'ReadConfig'
  if filereadable(s:stk_config_path)
    let s:stk_cfg_ts = getftime(s:stk_config_path)

    let l:json_content = join(readfile(s:stk_config_path), "\n")
    let s:stk_config = json_decode(l:json_content)
    if empty(s:stk_config['codes'])
      call s:Log('No stock code defined')
      return 0
    endif

    let s:stk_delay = (s:stk_config['delay'] + 1) * 1000

    return 1
  else
    call s:Log("Config file non-exist: " . s:stk_config_path)
    let l:data = {"codes": [], "indices": ["000001", "399001", "399006", "899050", "000985", "HSI"], "threshold": {"indices": [2, 3, 4, 5, 2, 3], "up": 7, "down": 5}, "delay": 6, "rest_dates": []}
    let l:json_content = json_encode(l:data)
    call writefile(split(l:json_content, "\n"), s:stk_config_path)
    return 0
  endif
endfunction

function! s:InRestDay(...)
  if a:0 == 0
    let l:timestamp = localtime()
  else
    let l:timestamp = a:1
  endif
  let l:date = strftime("%Y-%m-%d", l:timestamp)

  if !(str2nr(strftime("%w", l:timestamp)) % 6) || index(s:stk_config['rest_dates'], l:date) > -1
    "call s:Log((a:0 == 0 ? 'Today' : l:date) . ' is a rest day')
    return 1
  else
    return 0
  endif
endfunction

function! s:FindNextOpenDay()
  let l:timestamp = localtime()
  let l:days = 0
  while 1
    let l:days += 1
    let l:timestamp += 86400  "24 * 60 * 60
    if !s:InRestDay(l:timestamp)
      return l:days
    endif
  endwhile
endfunction

function! s:handle_stderr(data)
  for line in a:data
      if !empty(line)
          call s:LogErr(line)
      endif
  endfor
endfunction

function! s:StartRunner(check)
  "call s:Log('StartRunner')
  let l:failed = 0

  try
    if a:check && s:CheckRunner(0)
      throw ''
    endif

    call writefile([""], s:stk_runner_pid_path, 'b') " prevent newline

    let l:jobid = jobstart(["python", s:stk_runner_path], {'on_stderr': {job_id, data, event -> s:handle_stderr(data)}})

    if l:jobid == -1
      call s:LogErr("Runner not executable")
      let l:failed = 1
    elseif l:jobid == 0
      call s:LogErr("Runner with invalid arguments")
      let l:failed = 1
    endif

    if l:failed
      throw ''
    else
      let l:timestamp = localtime()
      let l:pid = string(jobpid(l:jobid))
      call s:Log("Runner started at " . string(l:timestamp) . ': ' . l:pid)
      call writefile([l:pid], s:stk_runner_pid_path)
    endif
  catch
    if v:exception != ''
      let l:failed = 1
      call s:LogErr(v:exception)
    endif
  finally
      if !l:failed
        let s:stk_timer = timer_start(2000, { -> s:WaitDisplay(0) })
      endif
  endtry
endfunction

function! s:WaitDisplay(timer)
  "call s:Log('WaitDisplay: ' . getftime(g:stk_data_path) . ' ' . s:stk_last_read_time)
  if filereadable(g:stk_data_path) && getftime(g:stk_data_path) > g:stk_last_read_time && getfsize(g:stk_data_path) > 0
    call s:DisplayPrices(0)
  else
    call s:Log('Update pending')
    let s:stk_timer = timer_start(1000, 's:WaitDisplay')
  endif
endfunction

" a:timer = 0: called directly once rather than intermittently at market time  
function! s:DisplayPrices(timer)
  "call s:Log('DisplayPrices')
  let l:tCfg = getftime(s:stk_config_path)
  if l:tCfg > s:stk_cfg_ts
    call s:ReadConfig()
    let s:stk_cfg_ts = l:tCfg
  endif

  let l:tData = getftime(g:stk_data_path)

  if !filereadable(s:stk_data_lock_path)
    let l:tLock = 12345678901 ":locked: one more digit
  else
    let l:tLock = getftime(s:stk_data_lock_path)
  endif
  "call s:Log('Lock/Data: ' . l:tLock . '/' . l:tData . ' >' . (l:tLock > l:tData) . ' timer:' . a:timer)
  if a:timer && l:tLock > l:tData
    call s:Log('Data locked (if loop, runner quit abruptly, go to verify then call <leader>su...)')
    let s:stk_timer = timer_start(1000, 's:DisplayPrices')
    return
  endif

  "call s:Log('Data age: ' . string(localtime() - l:tData))
  if a:timer && localtime() - l:tData > 60 " 1 min
    call s:Log("Data obsolete (runner crashed or wake from sleep)")
    call StockRun()
    return
  end 

  let l:updated = l:tData > g:stk_last_read_time
  let l:data = s:ReadData()
  "Only check runner if called in market time (by schedule) & data is not updated by runner
  let l:waiting = a:timer && !l:updated
  "call s:Log('modified data/last: ' . string(l:tData) . ' ' . string(g:stk_last_read_time) . ' a:timer: ' . string(a:timer))
  if l:waiting
    call s:Log('waiting: ' . string(l:tData) . ' ' . string(g:stk_last_read_time))
    if !s:CheckRunner(1)
      call s:StartRunner(0)
      return
    endif
  else
    if has_key(l:data, 'prices')
      if type(l:data['prices']) == v:t_string
        let l:error = "[STOCK] Error"
        let g:stk_output = s:CreateText(l:error, 'ErrorMsg')
        call s:LogErr("Runner: " . l:data['prices'])
      elseif !empty(l:data['prices'])
        let l:countIndices = len(s:stk_config['indices'])
        let l:ix = 0
        let l:text = ''

        for [name, value] in l:data['prices']
          if l:ix < l:countIndices
            if type(value) == v:t_string "- when non-exist
              let l:valueStr = value
            else
              let l:valueStr = string(value)
            endif
          else
            let l:valueStr = name . value
          endif

          let l:undefined = 0
          if l:ix < l:countIndices
            if type(value) == v:t_string && value == s:VAL_PLACEHOLDER
              let l:hl = 'stk_even'
            else
              let l:threshold = s:stk_config["threshold"]["indices"][ix]
              if value >= l:threshold
                let l:hl = 'stk_up_hl'
              elseif value <= -l:threshold
                let l:hl = 'stk_down_hl'
              else
                let l:undefined = 1
              endif
            endif
          else
            if value >= s:stk_config["threshold"]["up"]
              let l:hl = 'stk_up_hl'
            elseif value <= -s:stk_config["threshold"]["down"]
              let l:hl = 'stk_down_hl'
            else
              let l:undefined = 1
            endif
          endif

          if l:undefined
            if value == 0
              let l:hl = 'stk_even'
            elseif value > 0
              let l:hl = 'stk_up'
            else
              let l:hl = 'stk_down'
            endif
          endif

          let l:text = l:text . s:CreateText(l:valueStr, l:hl)

          if l:ix < l:countIndices
            let l:text = l:text . s:CreateText(l:ix == 2 ? s:stk_sep2 : s:stk_sep1, 'stk_even')
          endif

          let l:ix += 1
        endfor
        let g:stk_output = l:text
      else
        call s:Log('Prices empty')
      endif
    else
      call s:Log('No "Prices" key, data may be corrupted, or cleared when right open in runner, but here should not be reached, check dataLockFile logics')
    endif
  endif

  let l:target_days = 0
  let l:target_hour = 0
  if s:InRestDay()
    let l:target_days = s:FindNextOpenDay()
  else
    let l:timehour = strftime("%H%M%S") "Consistent with stocker_runner `datetime.now().time()`
    if l:timehour < "091500"
      let l:target_hour = 9
      let l:target_minute = 15
    elseif l:timehour > "113000" && l:timehour < "130000"
      let l:target_hour = 13
      let l:target_minute = 0
    elseif l:timehour > "150000"
      call s:Log('Market closed')
      let l:target_days = s:FindNextOpenDay()
    endif
  endif

  if l:target_days
    let l:min = (24 * l:target_days - str2nr(strftime("%H"))) * 60 - str2nr(strftime("%M"))
    let l:min += 9 * 60 + 15
    let s:stk_timer = timer_start(l:min * 60000, 's:StartRunner')
    call s:Log('Scheduled after ' . l:target_days . ' day(s) [' . strftime("%Y-%m-%d %a", localtime() + l:target_days * 86400) . ']')
  elseif l:target_hour
    let l:current_hour = str2nr(strftime("%H"))
    let l:current_minute = str2nr(strftime("%M"))
    let l:min = (l:target_hour - l:current_hour) * 60 + (l:target_minute - l:current_minute)
    let s:stk_timer = timer_start(l:min * 60000, 's:StartRunner')

    let l:hour = l:min / 60
    let l:min = l:min % 60
    call s:Log('Scheduled after ' . l:hour . ':' . l:min)
  else
    let s:stk_timer = timer_start(s:stk_delay, 's:DisplayPrices')
  endif

  "Display a correct one before quit
  "echom 'aaaa' . (l:target_days || l:target_hour)
  "echom 'bbbb' . (!has_key(l:data, 'prices') || type(l:data['prices']) == v:t_string)
  "echom 'cccc' . (s:stk_retry < 3)
  if (l:target_days || l:target_hour) && (!has_key(l:data, 'prices') || type(l:data['prices']) == v:t_string) && s:stk_retry < 3
    call s:Log('Retry ' . s:stk_retry)
    let s:stk_retry += 1
    let s:stk_timer = timer_start(s:stk_delay, 's:DisplayPrices')
  endif
endfunction

function! StockRun()
  "call s:Log('StockRun')
  if !s:ReadConfig()
    return
  endif

  let l:needRunner = 0
  let l:timehour = strftime("%H%M")

  if !filereadable(g:stk_data_path) || getfsize(g:stk_data_path) == 0
    let l:needRunner = 1
  else
    let l:data_modified_time = getftime(g:stk_data_path)
    let g:stk_last_read_time = localtime()
    "call s:Log('StockRun g:stk_last_read_time: ' . string(g:stk_last_read_time))

    if getftime(s:stk_config_path) > l:data_modified_time
      let l:needRunner = 1
    else
      let l:today_start = luaeval('GetMidnight()')
      if s:InRestDay()
        "strptime is not available on windows
        "Simpler way to ensure it's the latest
        if l:data_modified_time < l:today_start
          "call s:Log('data modified time: ' . l:data_modified_time . ' today start: ' . l:today_start)
          let l:needRunner = 1
        endif
      else
        let l:timehour = strftime("%H%M%S")
        if l:timehour < "091500"
          if l:data_modified_time < l:today_start
            let l:needRunner = 1
          endif
        elseif l:timehour >= "113000" && l:timehour < "130000"
          if l:data_modified_time < l:today_start + 11 * 3600 + 30 * 60
            let l:needRunner = 1
          endif
        elseif l:timehour >= "150000"
          if l:data_modified_time < l:today_start + 15 * 3600
            let l:needRunner = 1
          endif
        else
          "Trading time
          let l:needRunner = !s:CheckRunner(0)
        endif
      endif
    endif
  endif

  if l:needRunner
    call s:StartRunner(1)
  else
    call s:DisplayPrices(0)
  endif
endfunction

function! StockRefresh()
  "call s:Log('refreshing')
  call writefile([""], g:stk_data_path, 'b') " prevent newline
  call StockRun()
endfunction

function! StockUpdate()
  if s:stk_timer
    call timer_stop(s:stk_timer)
    let s:stk_timer = 0
  endif

  let l:pid = s:CheckRunner(1)
  if l:pid > 1
    call s:Log("Killing runner: " .. l:pid)
    lua vim.loop.kill(vim.fn['eval']('l:pid'), 9)
  endif
  call StockRefresh()
endfunction

function! StockClean()
  lua CloseDataInner()
endfunction

"Only display in the first window
function! StkCheckWin(str, _)
  return winnr() == 1 ? a:str : ''
endfunction

function! StockPrices()
  call s:Log(system("python " . s:stk_runner_path . ' price')[:-2])
endfunction

function! LualineFromStock()
  " % is escaped when use directly
  return g:stk_output
endfunction


autocmd VimEnter * call StockRun()
autocmd VimLeave * call StockClean()
nnoremap <Leader>su :call StockUpdate()<Enter>
nnoremap <Leader>sp :call StockPrices()<Enter>
