let g:stk_config_path = $HOME . '/.stock.cfg.json'
let g:stk_data_path = $HOME . '/.stock.dat.json'
let g:stk_data_lock_path = $HOME . '/.stock.dat.lock'
let g:stk_runner_lock_path = $HOME . '/.stock.runner.lock'
let g:stk_runner_path = expand('<sfile>:p:h') .. '/' .. "stock_runner.py"
let g:stk_config = {}
let g:stk_last_read_time = 0

function! Log(msg)
  echom "[STOCK-". strftime("%H:%M") . '] ' . a:msg
endfunction

function! LogErr(msg)
  echohl WarningMsg
  echom "[STOCK-". strftime("%H:%M") . ']ERROR: ' . a:msg
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

let g:stk_sep = '/'
call airline#parts#define_accent(g:stk_sep, 'even')

function! IsProcessRunning(pid)
  let l:running = 0

  python3 << EOF
import psutil
import vim

pid = int(vim.eval('a:pid'))
if pid > 0:
    try:
        ps = psutil.Process(pid)
        if ps.is_running() and ps.parent() and ps.parent().name() == 'nvim.exe':
            vim.command('let l:running = 1')
        else:
            vim.command('let l:running = 0')
    except psutil.NoSuchProcess:
        pass
EOF
  return l:running
endfunction

lua << EOF
local file_handle
function OpenDataFile()
    file_handle = io.open(vim.g.stk_data_path, 'r')
    if file_handle then
        file_handle:setvbuf("full", 4096)  -- Set buffer size for efficiency
        vim.api.nvim_command('call Log("Data file opened")')
    else
        vim.api.nvim_command('call LogErr("Failed to open data file")')
    end
end

-- Function to read the whole content of the file
function ReadDataInner()
    if not file_handle then
        OpenDataFile()
    end

    if file_handle then
        file_handle:seek("set")
        return file_handle:read("*all")
    else
        vim.api.nvim_command('call LogErr("File handle is not available")')
        return ""
    end
end
EOF

function! ReadData()
  let l:content = luaeval('ReadDataInner()')
  "echom 'data content: ' . l:content"
  let g:stk_last_read_time = localtime()
  if len(l:content) > 0
    return json_decode(l:content)
  else
    return {}
  endif
endfunction

function! ReadConfig()
  if filereadable(g:stk_config_path)
    let l:json_content = join(readfile(g:stk_config_path), "\n")
    let g:stk_config = json_decode(l:json_content)
    if empty(g:stk_config['codes'])
      call Log('No stock code defined')
      return 0
    else
      return 1
    endif
  else
    call Log("File does not exist: " . g:stk_config_path)
    let l:data = {"codes": [], "delay": 5, "threshold": {"indices": [2, 3, 4], "up": 7, "down": 5}, "rest_dates": []}
    let l:json_content = json_encode(l:data)
    call writefile(split(l:json_content, "\n"), g:stk_config_path)
    return 0
  endif
endfunction

function! InRest()
  if str2nr(strftime("%w")) > 5 || index(g:stk_config['rest_dates'], strftime("%Y-%m-%d")) > -1
    call Log('Today is a rest day')
    return 1
  else
    return 0
  endif
endfunction

function! StartRunner(check)
  let l:data = ReadData()

  try
    if a:check && has_key(l:data, 'runner_pid') && l:data['runner_pid'] > 0 && IsProcessRunning(l:data['runner_pid'])
      call Log("is already running")
      throw ''
    endif

    if filereadable(g:stk_runner_lock_path)
      call Log("Runner is starting by another instance")
      throw ''
    endif
    call writefile([], g:stk_runner_lock_path)
    let l:jobid = jobstart(["python", g:stk_runner_path])
    if l:jobid == -1
      call LogErr("runner not executable")
      throw ''
    elseif l:jobid == 0
      call LogErr("runner with invalid arguments")
      throw ''
    endif

    call delete(g:stk_runner_lock_path)
    call Log("Runner started")
  catch
    if v:exception != ''
      call LogErr(v:exception)
    endif
  finally
    call timer_start(2000, { -> WaitPrices(localtime()) })
  endtry
endfunction

function! WaitPrices(runner_time)
  "echom 'WaitPrices'"
  if getftime(g:stk_data_path) > a:runner_time
    call DisplayPrices(0)
  else
    call timer_start(1000, 'WaitPrices')
  endif
endfunction

function! DisplayPrices(timer)
  "echom 'DisplayPrices'"
  let l:tData = getftime(g:stk_data_path)
  let l:tLock = getftime(g:stk_data_lock_path)
  if l:tLock > l:tData
    call Log('Data is locked')
    call timer_start(500, 'DisplayPrices')
    return
  endif

  let l:updated = l:tData > g:stk_last_read_time
  let l:data = ReadData()
  "echom 'data: ' . string(l:data)"
  if !l:updated && !IsProcessRunning(l:data['runner_pid'])
    call StartRunner(0)
    return
  endif

  if has_key(l:data, 'prices')
    if type(l:data['prices']) == v:t_string
      let g:airline_section_c = "Error"
      call airline#update_statusline()
    elseif !empty(l:data['prices'])
      let l:ix = 0
      let l:names = []
      for [key, value] in l:data['prices']
        if l:ix < 3
          let key = string(value)
          let valueStr = key
        else
          let valueStr = key . value
        endif

        call add(l:names, key)
        if l:ix < 3
          call add(l:names, g:stk_sep)
        endif
        call airline#parts#define_text(key, valueStr)

        let l:undefined = 0
        if l:ix < 3
          let l:threshold = g:stk_config["threshold"]["indices"][ix]
          if value >= l:threshold
            call airline#parts#define_accent(key, 'up_hl')
          elseif value <= -l:threshold
            call airline#parts#define_accent(key, 'down_hl')
          else
            let l:undefined = 1
          endif
        else
          if value >= g:stk_config["threshold"]["up"]
            call airline#parts#define_accent(key, 'up_hl')
          elseif value <= -g:stk_config["threshold"]["down"]
            call airline#parts#define_accent(key, 'down_hl')
          else
            let l:undefined = 1
          endif
        endif

        if l:undefined
          if value == 0
            call airline#parts#define_accent(key, 'even')
          elseif value > 0
            call airline#parts#define_accent(key, 'up')
          else
            call airline#parts#define_accent(key, 'down')
          endif
        endif

        let l:ix += 1
      endfor
      let g:airline_section_c = airline#section#create(l:names)
      call airline#update_statusline()
    else
      call Log('No prices')
    endif
  else
    call Log('No prices')
  endif

  if InRest()
    return
  endif

  let l:target_hour = 0
  let l:timehour = strftime("%H%M")
  if l:timehour < "0915"
    let l:target_hour = 9
    let l:target_minute = 15
  elseif l:timehour > "1130" && l:timehour < "1300"
    let l:target_hour = 13
    let l:target_minute = 0
  elseif l:timehour > "1500"
    call Log('Market closed')
    return
  endif

  if l:target_hour
    let l:current_hour = str2nr(strftime("%H"))
    let l:current_minute = str2nr(strftime("%M"))
    let l:min = (l:target_hour - l:current_hour) * 60 + (l:target_minute - l:current_minute)
    call timer_start(l:min * 60000, 'StartRunner')

    let l:hour = l:min / 60
    let l:min = l:min % 60
    call Log('scheduled after ' . l:hour . ':' . l:min)
  else
    call timer_start(g:stk_config['delay'] * 1000, 'DisplayPrices')
  endif
endfunction

function! Main()
  if ReadConfig()
    let l:needRunner = 0
    let l:timehour = strftime("%H%M")

    if InRest() || l:timehour < "0915" || l:timehour > "1130" && l:timehour < "1300" || l:timehour > "1500"
      let l:data_modified_time = getftime(g:stk_data_path)
      if getftime(g:stk_config_path) > l:data_modified_time
        let l:needRunner = 1
      else
        let l:today_start = strptime('%Y-%m-%d', strftime('%Y-%m-%d', localtime()))

        if l:data_modified_time < l:today_start
          let l:needRunner = 1
        endif
      endif
    else
      let l:needRunner = 1
    endif

    if l:needRunner
      call StartRunner(1)
    else
      call DisplayPrices(0)
    endif
  endif
endfunction

call Main()
