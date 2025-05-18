package log

import (
	"fmt"
	"time"
)

var LogLevel int // 0=silent, 1=error, 2=warn, 3=debug

func Info(msg string) {
	now := time.Now().Format("15:04:05")
	if LogLevel >= 1 {
		fmt.Printf("\u001b[38;5;244m%s\u001b[0m \u001b[36mINFO\u001b[0m %v\n", now, msg)
	}
}

func Success(msg string) {
	now := time.Now().Format("15:04:05")
	if LogLevel >= 1 {
		fmt.Printf("\u001b[38;5;244m%s\u001b[0m \u001b[32mOK  \u001b[0m %v\n", now, msg)
	}
}

func SYSWarn(msg string) {
	now := time.Now().Format("15:04:05")
	if LogLevel >= 2 {
		fmt.Printf("\u001b[38;5;244m%s\u001b[0m \u001b[33mSYSW\u001b[0m %v\n", now, msg)
	}
}

func APPWarn(msg string) {
	now := time.Now().Format("15:04:05")
	if LogLevel >= 2 {
		fmt.Printf("\u001b[38;5;244m%s\u001b[0m \u001b[33mAPPW\u001b[0m %v\n", now, msg)
	}
}

func Err(msg string) {
	now := time.Now().Format("15:04:05")
	if LogLevel >= 1 {
		fmt.Printf("\u001b[38;5;244m%s\u001b[0m \u001b[31mERRO\u001b[0m %v\n", now, msg)
	}
}

func Debug(msg string) {
	now := time.Now().Format("15:04:05")
	if LogLevel >= 3 {
		fmt.Printf("\u001b[38;5;244m%s\u001b[0m \u001b[35mDEBG\u001b[0m %v\n", now, msg)
	}
}
