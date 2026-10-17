"""Behavioural OV5640 register/SRAM model for protocol tests."""
class SensorBus:
    def __init__(self, corrupt=None):
        self.registers={};self.firmware_blocks=[];self.commands=[]
        self.corrupt=corrupt;self.focus_reads=0

    def transfer(self,address,write=b'',read=0):
        if address!=0x3c:raise IOError('Unexpected camera address')
        reg=(write[0]<<8)|write[1]
        if reg>=0x8000 and self.registers.get(0x3004,0)&0x60!=0x60:
            raise IOError('AF SRAM clocks are gated')
        if read:
            if reg==0x3029 and self.commands and self.commands[-1]==3:
                self.focus_reads+=1
                if self.focus_reads>1:self.registers[reg]=0x10
            values=[self.registers.get(reg+i,0)^(1 if reg+i==self.corrupt else 0) for i in range(read)]
            return bytes(values)
        data=write[2:]
        if reg>=0x8000:self.firmware_blocks.append((reg,bytes(data)))
        for i,value in enumerate(data):self.registers[reg+i]=value
        if reg==0x3000 and data==b'\x00':
            self.registers[0x3029]=0x70
            self.registers[0x3004]&=~0x40
        if reg==0x3022 and data and data[0] in (3,4,8):
            if self.registers.get(0x3004,0)&0x60!=0x60:raise IOError('AF MCU clock is gated')
            self.commands.append(data[0]);self.registers[0x3023]=0
            self.registers[0x3029]=0x70 if data[0]==8 else 0
            if data[0]==8:self.registers[0x3004]&=~0x40
        return b''

