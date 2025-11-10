//toggle component
import React from 'react'

const Toggle = ({ mode, setMode, disabled = false }) => {
  const isChecked = mode === "EDI"

  const handleCheckboxChange = () => {
    if (disabled) return
    const nextMode = isChecked ? "PROCEDURE" : "EDI"
    setMode(nextMode)
  }

  const handleOptionSelect = (nextMode, event) => {
    if (event) {
      event.preventDefault()
      event.stopPropagation()
    }
    if (disabled || nextMode === mode) return
    setMode(nextMode)
  }

  const handleKeyDown = (event, nextMode) => {
    if (disabled) return
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      handleOptionSelect(nextMode)
    }
  }

  return (
    <>
      <label
        className='themeSwitcherTwo shadow-card relative inline-flex cursor-pointer select-none items-center justify-center rounded-md bg-white p-1'
        aria-disabled={disabled}
      >
        <input
          type='checkbox'
          className='sr-only'
          checked={isChecked}
          onChange={handleCheckboxChange}
          disabled={disabled}
        />
        <span
          className={`flex items-center space-x-[6px] rounded py-2 px-[18px] text-sm font-medium ${
            isChecked ? 'text-primary bg-[#f4f7ff]' : 'text-body-color'
          }`}
          onClick={(event) => handleOptionSelect("EDI", event)}
          role="button"
          tabIndex={disabled ? -1 : 0}
          onKeyDown={(event) => handleKeyDown(event, "EDI")}
          aria-pressed={isChecked}
        >
          <svg
            width='16'
            height='16'
            viewBox='0 0 16 16'
            className='mr-[6px] fill-current'
          >
            <path
              fillRule='evenodd'
              clipRule='evenodd'
              d='M8 0C3.58172 0 0 3.58172 0 8C0 12.4183 3.58172 16 8 16C12.4183 16 16 12.4183 16 8C16 3.58172 12.4183 0 8 0ZM8 1.5C11.5899 1.5 14.5 4.41015 14.5 8C14.5 11.5899 11.5899 14.5 8 14.5C4.41015 14.5 1.5 11.5899 1.5 8C1.5 4.41015 4.41015 1.5 8 1.5ZM8 3C5.23858 3 3 5.23858 3 8C3 10.7614 5.23858 13 8 13C10.7614 13 13 10.7614 13 8C13 5.23858 10.7614 3 8 3ZM8 4.5C9.933 4.5 11.5 6.067 11.5 8C11.5 9.933 9.933 11.5 8 11.5C6.067 11.5 4.5 9.933 4.5 8C4.5 6.067 6.067 4.5 8 4.5ZM8 6C7.17157 6 6.5 6.67157 6.5 7.5V8.5C6.5 9.32843 7.17157 10 8 10C8.82843 10 9.5 9.32843 9.5 8.5V7.5C9.5 6.67157 8.82843 6 8 6ZM8 7C8.27614 7 8.5 7.22386 8.5 7.5V8.5C8.5 8.77614 8.27614 9 8 9C7.72386 9 7.5 8.77614 7.5 8.5V7.5C7.5 7.22386 7.72386 7 8 7Z'
            />
          </svg>
          EDI Mode
        </span>
        <span
          className={`flex items-center space-x-[6px] rounded py-2 px-[18px] text-sm font-medium ${
            !isChecked ? 'text-primary bg-[#f4f7ff]' : 'text-body-color'
          }`}
          onClick={(event) => handleOptionSelect("PROCEDURE", event)}
          role="button"
          tabIndex={disabled ? -1 : 0}
          onKeyDown={(event) => handleKeyDown(event, "PROCEDURE")}
          aria-pressed={!isChecked}
        >
          <svg
            width='16'
            height='16'
            viewBox='0 0 16 16' 
            className='mr-[6px] fill-current'
          >
            <path
              fillRule='evenodd'
              clipRule='evenodd'
              d='M2 1C1.44772 1 1 1.44772 1 2V14C1 14.5523 1.44772 15 2 15H14C14.5523 15 15 14.5523 15 14V2C15 1.44772 14.5523 1 14 1H2ZM2 2H14V14H2V2ZM3 3V13H13V3H3ZM4 4H12V5H4V4ZM4 6H12V7H4V6ZM4 8H12V9H4V8ZM4 10H12V11H4V10ZM4 12H12V13H4V12Z'
            />
          </svg>
          Process Manual Mode
        </span>
      </label>
    </>
  )
}

export default Toggle
