" rest_dates
" http://tools.2345.com/rili.htm
" formateJxData()

let g:stk_folder = $HOME . '/.stock'
if !isdirectory(g:stk_folder)
  call mkdir(g:stk_folder)
  call mkdir(g:stk_folder . '/cfg')
endif

let g:stk_config_path = g:stk_folder . '/cfg/stock.cfg.json'
let g:stk_data_path = g:stk_folder. '/stock.dat.json'
let g:stk_data_lock_path = g:stk_folder . '/stock.dat.lock'
let g:stk_runner_pid_path = g:stk_folder . '/stock.runner.pid'
let g:stk_runner_path = expand('<sfile>:p:h') . "/stock_runner.py"
let g:stk_config = {}
let g:stk_last_read_time = 0
let g:stk_cfg_ts = 0
let g:stk_timer = 0
let g:stk_output = ''

function! s:Log(msg)
  echom "[STOCK-". strftime("%m/%d %H:%M:%S") . '] ' . a:msg
endfunction

function! s:LogErr(msg)
  echohl WarningMsg
  echom "[STOCK-". strftime("%m/%d %H:%M:%S") . ']ERROR: ' . a:msg
  echohl None
endfunction

function! AirlineThemePatch(palette)
  let a:palette.accents.up = [ '#5d6b00', '', 0, '', '' ]
  let a:palette.accents.up_hl = [ '#cb4b16', '', 0, '', 'bold' ]
  let a:palette.accents.down = [ '#1d7069', '', 0, '', '' ]
  let a:palette.accents.down_hl = [ '#268bdc', '', 0, '', 'bold' ]
  let a:palette.accents.even = [ '#586e6b', '', 0, '', '' ]
endfunction
let g:airline_theme_patch_func = 'AirlineThemePatch'
call airline#highlighter#add_accent('up')
call airline#highlighter#add_accent('up_hl')
call airline#highlighter#add_accent('down')
call airline#highlighter#add_accent('down_hl')
call airline#highlighter#add_accent('even')

let g:stk_sep1 = '/'
let g:stk_sep2 = '|'
call airline#parts#define_accent(g:stk_sep1, 'even')
call airline#parts#define_accent(g:stk_sep2, 'even')

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

function! s:CheckRunner()
  if filereadable(g:stk_runner_pid_path)
    if getfsize(g:stk_runner_pid_path) > 0
      let l:pid = readfile(g:stk_runner_pid_path)[0]
      "echom 'pid: ' . l:pid
      if s:IsProcessRunning(l:pid)
        call s:Log("Runner is already running")
        return l:pid
      endif
    else
      call s:Log("Runner is starting by another instance")
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
        vim.api.nvim_command('call s:Log("Data file opened")')
    else
        vim.api.nvim_command('call s:LogErr("Failed to open data file")')
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
        vim.api.nvim_command('call s:LogErr("File handle is not available")')
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
  local function on_exit(code, signal)
    if code ~= 0 then
      vim.schedule(function()
        vim.api.nvim_echo({{"Failed to kill PID: "..pid.." (code "..code..")", "ErrorMsg"}}, true, {})
      end)
    else
      CloseDataInner()
      vim.fn.StockRun()
    end
  end

  local ok, err = pcall(function()
    vim.loop.kill(pid, 15, on_exit)
  end)

  if not ok then
    vim.schedule(function()
      vim.api.nvim_echo({{"Failed to invoke 'pcall', Lua error: "..err, "ErrorMsg"}}, true, {})
    end)
  end
end

EOF

function! s:ReadData()
  let l:content = luaeval('ReadDataInner()')
  "echom 'data content: ' . l:content
  let g:stk_last_read_time = localtime()
  if len(l:content) > 0
    return json_decode(l:content)
  else
    return {}
  endif
endfunction

function! s:ReadConfig()
  "echom 'ReadConfig'
  if filereadable(g:stk_config_path)
    let g:stk_cfg_ts = getftime(g:stk_config_path)

    let l:json_content = join(readfile(g:stk_config_path), "\n")
    let g:stk_config = json_decode(l:json_content)
    if empty(g:stk_config['codes'])
      call s:Log('No stock code defined')
      return 0
    endif
    return 1
  else
    call s:Log("File does not exist: " . g:stk_config_path)
    let l:data = {"codes": [], "indices": ["000001", "399001", "399006", "899050", "000985", "HSI"], "threshold": {"indices": [2, 3, 4, 5, 2, 3], "up": 7, "down": 5}, "delay": 6, "rest_dates": []}
    let l:json_content = json_encode(l:data)
    call writefile(split(l:json_content, "\n"), g:stk_config_path)
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

  if !(str2nr(strftime("%w", l:timestamp)) % 6) || index(g:stk_config['rest_dates'], l:date) > -1
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
  "echom 'StartRunner'
  let l:failed = 0

  try
    if a:check && s:CheckRunner()
      throw ''
    endif

    call writefile([""], g:stk_runner_pid_path, 'b') " prevent newline

    let l:jobid = jobstart(["python", g:stk_runner_path], {'on_stderr': {job_id, data, event -> s:handle_stderr(data)}})

    if l:jobid == -1
      call s:LogErr("runner not executable")
      let l:failed = 1
    elseif l:jobid == 0
      call s:LogErr("runner with invalid arguments")
      let l:failed = 1
    endif

    if l:failed
      throw ''
    else
      let l:timestamp = localtime()
      call s:Log("Runner started at " . string(l:timestamp))
      call writefile([string(jobpid(l:jobid))], g:stk_runner_pid_path)
    endif
  catch
    if v:exception != ''
      let l:failed = 1
      call s:LogErr(v:exception)
    endif
  finally
      if !l:failed
        let g:stk_timer = timer_start(2000, { -> s:WaitDisplay(0) })
      endif
  endtry
endfunction

function! s:WaitDisplay(timer)
  "echom 'WaitDisplay'
  " echom getftime(g:stk_data_path) . ' ' . g:stk_last_read_time
  if getftime(g:stk_data_path) > g:stk_last_read_time
    call s:DisplayPrices(0)
  else
    call s:Log('Update is pending')
    let g:stk_timer = timer_start(1000, 's:WaitDisplay')
  endif
endfunction

function! s:DisplayPrices(timer)
  "echom 'DisplayPrices'
  let l:tCfg = getftime(g:stk_config_path)
  if l:tCfg > g:stk_cfg_ts
    call s:ReadConfig()
    let g:stk_cfg_ts = l:tCfg
  endif

  let l:tData = getftime(g:stk_data_path)

  if !filereadable(g:stk_data_lock_path)
    let l:tLock = 12345678901 ":locked
  else
    let l:tLock = getftime(g:stk_data_lock_path)
  endif
  "echom 'Lock/Data: ' . string(l:tLock) . '/' . string(l:tData)
  if l:tLock > l:tData
    call s:Log('Data is locked (if loop, runner quit abruptly, go to verify then call <leader>su...)')
    let g:stk_timer = timer_start(1000, 's:DisplayPrices')
    return
  endif

  let l:updated = l:tData > g:stk_last_read_time
  let l:data = s:ReadData()
  "Only check runner if called in market time (by schedule) & data is not updated by runner
  let l:waiting = a:timer && !l:updated
  "echom 'modified data/last: ' string(l:tData) . ' ' . string(g:stk_last_read_time)
  "echom 'a:timer: ' . string(a:timer)
  if l:waiting
    "echom 'waiting: ' string(l:tData) . ' ' . string(g:stk_last_read_time)
    if !s:CheckRunner()
      call s:StartRunner(0)
      return
    endif
  else
    if has_key(l:data, 'prices')
      if type(l:data['prices']) == v:t_string
        let l:error = "[STOCK] Error"
        call airline#parts#define_accent(l:error, 'red')
        call airline#parts#define_text(l:error, l:error) " At least on %{}% should appear, otherwise nothing is displayed
        let g:airline_section_c = airline#section#create(l:error)
        call airline#update_statusline()
        call s:LogErr("Runner: " . l:data['prices'])
      elseif !empty(l:data['prices'])
        let l:countIndices = len(g:stk_config['indices'])
        let l:ix = 0
        let l:text = []

        for [name, value] in l:data['prices']
          if l:ix < l:countIndices
            if type(value) == v:t_string "- when non-exist
              let name = value
            else
              let name = string(value)
            endif
            let valueStr = name
          else
            let valueStr = name . value
          endif

          call add(l:text, name)
          if l:ix < l:countIndices
            if l:ix == 2
              call add(l:text, g:stk_sep2)
            else
              call add(l:text, g:stk_sep1)
            endif
          endif
          call airline#parts#define_text(name, valueStr)

          let l:undefined = 0
          if l:ix < l:countIndices
            if type(value) == v:t_string && value == '-'
              call airline#parts#define_accent(name, 'even')
            else
              let l:threshold = g:stk_config["threshold"]["indices"][ix]
              if value >= l:threshold
                call airline#parts#define_accent(name, 'up_hl')
              elseif value <= -l:threshold
                call airline#parts#define_accent(name, 'down_hl')
              else
                let l:undefined = 1
              endif
            endif
          else
            if value >= g:stk_config["threshold"]["up"]
              call airline#parts#define_accent(name, 'up_hl')
            elseif value <= -g:stk_config["threshold"]["down"]
              call airline#parts#define_accent(name, 'down_hl')
            else
              let l:undefined = 1
            endif
          endif

          if l:undefined
            if value == 0
              call airline#parts#define_accent(name, 'even')
            elseif value > 0
              call airline#parts#define_accent(name, 'up')
            else
              call airline#parts#define_accent(name, 'down')
            endif
          endif

          let l:ix += 1
        endfor
        let g:airline_section_c = substitute(airline#section#create(l:text), 'airline#util#wrap', 'StkCheckWin', 'g')
        call airline#update_statusline()
      else
        call s:Log('Prices are empty')
      endif
    else
      call s:Log('No prices yet')
    endif
  endif

  let l:target_days = 0
  let l:target_hour = 0
  if s:InRestDay()
    let l:target_days = s:FindNextOpenDay()
  else
    let l:timehour = strftime("%H%M")
    if l:timehour < "0915"
      let l:target_hour = 9
      let l:target_minute = 15
    elseif l:timehour >= "1130" && l:timehour < "1300"
      let l:target_hour = 13
      let l:target_minute = 0
    elseif l:timehour >= "1600"
      call s:Log('Market closed')
      let l:target_days = s:FindNextOpenDay()
    endif
  endif

  if l:target_days
    let l:min = (24 * l:target_days - str2nr(strftime("%H"))) * 60 - str2nr(strftime("%M"))
    let l:min += 9 * 60 + 15
    let g:stk_timer = timer_start(l:min * 60000, 's:StartRunner')
    call s:Log('Scheduled after ' . l:target_days . ' day(s) [' . strftime("%Y-%m-%d %a", localtime() + l:target_days * 86400) . ']')
  elseif l:target_hour
    let l:current_hour = str2nr(strftime("%H"))
    let l:current_minute = str2nr(strftime("%M"))
    let l:min = (l:target_hour - l:current_hour) * 60 + (l:target_minute - l:current_minute)
    let g:stk_timer = timer_start(l:min * 60000, 's:StartRunner')

    let l:hour = l:min / 60
    let l:min = l:min % 60
    call s:Log('Scheduled after ' . l:hour . ':' . l:min)
  else
    let g:stk_timer = timer_start(g:stk_config['delay'] * 1000, 's:DisplayPrices')
  endif
endfunction

function! StockRun()
  if !s:ReadConfig()
    return
  endif

  let l:needRunner = 0
  let l:timehour = strftime("%H%M")

  let l:data_modified_time = getftime(g:stk_data_path)
  let g:stk_last_read_time = localtime()
  if getftime(g:stk_config_path) > l:data_modified_time
    let l:needRunner = 1
  else
    let l:today_start = luaeval('GetMidnight()')
    if s:InRestDay()
      "strptime is not available on windows
      "Simpler way to ensure it's the latest
      if l:data_modified_time < l:today_start
        "echom 'data modified time: ' . l:data_modified_time . ' today start: ' . l:today_start
        let l:needRunner = 1
      endif
    else
      let l:timehour = strftime("%H%M")
      if l:timehour < "0915"
        if l:data_modified_time < l:today_start
          let l:needRunner = 1
        endif
      elseif l:timehour >= "1130" && l:timehour < "1300"
        if l:data_modified_time < l:today_start + 11 * 3600 + 30 * 60
          let l:needRunner = 1
        endif
      elseif l:timehour >= "1600"
        if l:data_modified_time < l:today_start + 16 * 3600
          let l:needRunner = 1
        endif
      else
        "Trading time
        let l:needRunner = !s:CheckRunner()
      endif
    endif
  endif

  if l:needRunner
    call s:StartRunner(1)
  else
    call s:DisplayPrices(0)
  endif
endfunction

function! StockUpdate()
  if g:stk_timer
    call timer_stop(g:stk_timer)
    let g:stk_timer = 0
  endif

  let l:pid = s:CheckRunner()
  if l:pid > 1
    lua KillPid(vim.fn.eval('l:pid'))
  else
    lua CloseDataInner()
    call StockRun()
  endif
endfunction

function! StockClean()
  lua CloseDataInner()
endfunction

"Only display in the first window
function! StkCheckWin(str, _)
  return winnr() == 1 ? a:str : ''
endfunction

function! StockPrices()
  call s:Log(system("python " . g:stk_runner_path . ' price')[:-2])
endfunction


autocmd VimEnter * call StockRun()
autocmd VimLeave * call StockClean()
nnoremap <Leader>su :call StockUpdate()<Enter>
nnoremap <Leader>sp :call StockPrices()<Enter>
