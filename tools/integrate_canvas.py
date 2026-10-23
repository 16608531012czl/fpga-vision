"""One-time, checked integration of the independent canvas AXI master."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'rtl/visual_aid_core.sv';text=p.read_text()
assert 'm_canvas_awaddr' not in text
signals=[('awaddr',32,'output'),('awlen',8,'output'),('awsize',3,'output'),
         ('awburst',2,'output'),('awcache',4,'output'),('awprot',3,'output'),
         ('awlock',1,'output'),('awvalid',1,'output'),('awready',1,'input'),
         ('wdata',32,'output'),('wstrb',4,'output'),('wlast',1,'output'),
         ('wvalid',1,'output'),('wready',1,'input'),('bresp',2,'input'),
         ('bvalid',1,'input'),('bready',1,'output')]
ports=[]
for name,width,direction in signals:
 attr='(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_canvas '+name.upper()+'"'
 if name=='awaddr':attr+=', X_INTERFACE_PARAMETER="PROTOCOL AXI4, DATA_WIDTH 32, ADDR_WIDTH 32"'
 attr+=' *) '
 ports.append(attr+direction+' wire '+(('['+str(width-1)+':0] ') if width>1 else '')+'m_canvas_'+name)
old='output wire m_axis_tlast);'
assert old in text
text=text.replace(old,'output wire m_axis_tlast,\n '+',\n '.join(ports)+');')
text=text.replace('s_axi:m_axi:s_axis:m_axis','s_axi:m_axi:m_canvas:s_axis:m_axis')
marker='wire [31:0] quality_word;'
text=text.replace(marker,marker+'\nwire [31:0] canvas_destination,view_cfg,roi_cfg;\nwire raw_busy,raw_done,raw_error,raw_ready,canvas_busy,canvas_done,canvas_error,canvas_ready_internal;\nwire [31:0] raw_errors,canvas_errors;\nwire canvas_on=view_cfg[7];\nwire canvas_ready=!canvas_on||canvas_ready_internal;\nassign capture_ready=raw_ready&&canvas_ready;\nassign busy=raw_busy||canvas_busy;assign done=raw_done&&(!canvas_on||canvas_done);\nassign error=raw_error||canvas_error;assign dma_errors=raw_errors+canvas_errors;')
text=text.replace('.quality_word(quality_word));','.quality_word(quality_word),.canvas_destination(canvas_destination),.view_cfg(view_cfg),.roi_cfg(roi_cfg),.canvas_status({29\'d0,canvas_error,canvas_done,canvas_busy}));',1)
text=text.replace('.s_data(capture_data),.s_valid(capture_valid),.s_ready(capture_ready),',
                  '.s_data(capture_data),.s_valid(capture_valid&&canvas_ready),.s_ready(raw_ready),')
text=text.replace('.busy(busy),.done(done),.error(error),.frame_id(frame_id),.error_count(dma_errors),',
                  '.busy(raw_busy),.done(raw_done),.error(raw_error),.frame_id(frame_id),.error_count(raw_errors),')
instance='\ncanvas_writer #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) canvas(\n.clk(aclk),.resetn(aresetn),.enable(enable&&canvas_on),.start(start&&canvas_on),\n.destination(canvas_destination),.view_cfg(view_cfg),.roi_cfg(roi_cfg),\n.s_data(capture_data),.s_valid(capture_valid&&raw_ready&&canvas_on),.s_ready(canvas_ready_internal),\n.busy(canvas_busy),.done(canvas_done),.error(canvas_error),.errors(canvas_errors),\n'
instance+=',\n'.join('.'+name+'(m_canvas_'+name+')' for name,_,_ in signals)+');\n'
text=text.replace('reading_enhance #',instance+'reading_enhance #')
p.write_text(text,encoding='utf-8')
print('Canvas master integrated')
