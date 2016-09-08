#!/usr/bin/env python
# -*- coding: utf-8 -*-

import spidev,time
import sys,cmd,shlex,types
from mcp2515 import *

spi = spidev.SpiDev(0,0)

def mcp2515_reset():
    tmpc = [0xc0]
    spi.writebytes(tmpc)
    
def mcp2515_writeReg(addr, val):
    buf = [0x02, addr, val]
    spi.writebytes(buf)

def mcp2515_readReg(addr):
    buf = [0x03, addr, 0x55]
    buf = spi.xfer2(buf)
    return int(buf[2])

def mcp2515_init():
    mcp2515_reset()
    time.sleep(2)
    #设置波特率为125Kbps
    #set CNF1,SJW=00,长度为1TQ,BRP=49,TQ=[2*(BRP+1)]/Fsoc=2*50/8M=12.5us
    mcp2515_writeReg(CNF1,CAN_125Kbps);
    #set CNF2,SAM=0,在采样点对总线进行一次采样，PHSEG1=(2+1)TQ=3TQ,PRSEG=(0+1)TQ=1TQ
    mcp2515_writeReg(CNF2,0x80|PHSEG1_3TQ|PRSEG_1TQ);
    #set CNF3,PHSEG2=(2+1)TQ=3TQ,同时当CANCTRL.CLKEN=1时设定CLKOUT引脚为时间输出使能位
    mcp2515_writeReg(CNF3,PHSEG2_3TQ);
	
    mcp2515_writeReg(TXB0SIDH,0xFF)#发送缓冲器0标准标识符高位
    mcp2515_writeReg(TXB0SIDL,0xEB)#发送缓冲器0标准标识符低位(第3位为发送拓展标识符使能位)
    mcp2515_writeReg(TXB0EID8,0xFF)#发送缓冲器0拓展标识符高位
    mcp2515_writeReg(TXB0EID0,0xFF)#发送缓冲器0拓展标识符低位
	
    mcp2515_writeReg(RXB0SIDH,0x00)#清空接收缓冲器0的标准标识符高位
    mcp2515_writeReg(RXB0SIDL,0x00)#清空接收缓冲器0的标准标识符低位
    mcp2515_writeReg(RXB0EID8,0x00)#清空接收缓冲器0的拓展标识符高位
    mcp2515_writeReg(RXB0EID0,0x00)#清空接收缓冲器0的拓展标识符低位
    mcp2515_writeReg(RXB0CTRL,0x40)#仅仅接收拓展标识符的有效信息
    mcp2515_writeReg(RXB0DLC,DLC_8)#设置接收数据的长度为8个字节
	
    mcp2515_writeReg(RXF0SIDH,0xFF)#配置验收滤波寄存器n标准标识符高位
    mcp2515_writeReg(RXF0SIDL,0xEB)#配置验收滤波寄存器n标准标识符低位(第3位为接收拓展标识符使能位)
    mcp2515_writeReg(RXF0EID8,0xFF)#配置验收滤波寄存器n拓展标识符高位
    mcp2515_writeReg(RXF0EID0,0xFF)#配置验收滤波寄存器n拓展标识符低位

    mcp2515_writeReg(RXM0SIDH,0xFF)#配置验收屏蔽寄存器n标准标识符高位
    mcp2515_writeReg(RXM0SIDL,0xE3)#配置验收屏蔽寄存器n标准标识符低位
    mcp2515_writeReg(RXM0EID8,0xFF)#配置验收滤波寄存器n拓展标识符高位
    mcp2515_writeReg(RXM0EID0,0xFF)#配置验收滤波寄存器n拓展标识符低位
	
    mcp2515_writeReg(CANINTF,0x00)#清空CAN中断标志寄存器的所有位(必须由MCU清空)
    mcp2515_writeReg(CANINTE,0x01)#配置CAN中断使能寄存器的接收缓冲器0满中断使能,其它位禁止中断
	
    mcp2515_writeReg(CANCTRL,REQOP_NORMAL|CLKOUT_ENABLED)#将MCP2515设置为正常模式,退出配置模式
	
    #tmpc = mcp2515_readReg(CANSTAT)#读取CAN状态寄存器的值
    #tmpd = int(tmpc[0]) & 0xe0
    #if OPMODE_NORMAL!=tmpd:#判断MCP2515是否已经进入正常模式
    #    mcp2515_writeReg(CANCTRL,REQOP_NORMAL|CLKOUT_ENABLED)#再次将MCP2515设置为XX模式,退出配置模式
    print '\r\nMCP2515 Initialized.\r\n'


def mcp2515_write(buf):
    for i in range(50):
        time.sleep(2) #通过软件延时约nms(不准确)
        if not mcp2515_readReg(TXB0CTRL)&0x08:#快速读某些状态指令,等待TXREQ标志清零
            break
    N = len(buf)
    for j in range(N):
        mcp2515_writeReg(TXB0D0+j,buf[j])#将待发送的数据写入发送缓冲寄存器

    mcp2515_writeReg(TXB0DLC,N)#将本帧待发送的数据长度写入发送缓冲器0的发送长度寄存器
    mcp2515_writeReg(TXB0CTRL,0x08)#请求发送报文

def mcp2515_read():
    N = 0
    buf = []
    if mcp2515_readReg(CANINTF) & 0x01:
        N = mcp2515_readReg(RXB0DLC)#读取接收缓冲器0接收到的数据长度(0~8个字节)
        for i in range(N):
            buf.append(mcp2515_readReg(RXB0D0+i))#把CAN接收到的数据放入指定缓冲区
	mcp2515_writeReg(CANINTF,0)#清除中断标志位(中断标志寄存器必须由MCU清零)
	return buf

class MyCmd(cmd.Cmd):
    def __init__(self):
        cmd.Cmd.__init__(self)
        self.prompt='wyq@rpi2 ~ $ '
        mcp2515_init()

    def emptyline(self):
        pass

    def do_test(self,arg):
        lex = shlex.shlex(arg)
        for x in lex:
            print x

    def do_exit(self,arg):
        return True

    def do_mcp(self,arg):
        lex = shlex.shlex(arg)
        try:
            for x in lex:
                if x=='-':
                    opt = lex.next()
                    if opt.lower()=='init':
                        mcp2515_init()
                    elif opt.lower()=='w':
                        buf = []
                        for i in lex:
                            buf.append(int(i))
                        mcp2515_write(buf)
                    elif opt.lower()=='r':
                        buf = mcp2515_read()
                        print 'Received:',len(buf)
                        for i in buf:
                            print hex(int(i))
                    else:
                        pass
        except BaseException, e:
            print e
    
    def do_help(self,arg):
        print '基于MCP2515的CAN收发控制器'
        print 'Author:汪永强 QQ:917888229 Date:2016-8-18'
        print '发送指令: mcp -w XX YY ZZ'
        print '接收指令: mcp -r'
        print '重初始化: mcp -init'


if __name__=='__main__':
    mycmd = MyCmd()
    mycmd.cmdloop()
