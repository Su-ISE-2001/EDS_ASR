import os
import pickle

from matplotlib import pyplot as plot
import logging
from logging.handlers import RotatingFileHandler

from .apreo_common import *
from .tkinter_funcs import get_number_input, get_str_input

os.makedirs('../logs', exist_ok=True)
log_format = logging.Formatter('%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d]: %(message)s')
file_handler = RotatingFileHandler(
    f'logs/{Path(__file__).stem}.log',
    maxBytes=10 * 1024 * 1024,
    backupCount=5
)
file_handler.setFormatter(log_format)
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_format)
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(console_handler)


def pretty_pandas():
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', None)
    pd.set_option('display.precision', 2)
    pd.set_option('display.unicode.ambiguous_as_wide', True)
    pd.set_option('display.unicode.east_asian_width', True)


def get_sem_parameters():
    mag_n_ = get_number_input(prompt="放大倍数", default_val=1500)
    interval_mm_ = get_number_input(prompt="移动间隔(mm)", default_val=0.090)
    interval_m_ = interval_mm_ / 1000
    move_cnt_w_ = int(get_number_input(prompt="横向移动次数", default_val=10))
    move_cnt_h_ = int(get_number_input(prompt="纵向移动次数", default_val=10))
    sem_resolution_ = get_str_input(prompt="EDS分辨率(宽x高)", default_val="768x512", pattern=r"(\d+\s*)x(\s*\d+)")
    resolution_w_ = int(sem_resolution_.split("x")[0].strip())
    resolution_h_ = int(sem_resolution_.split("x")[1].strip())
    dwell_time_us_ = get_number_input(prompt="EDS像素停留时间(us)", default_val=20.0)
    dwell_time_s_ = dwell_time_us_ / 1000000
    frames_n_ = int(get_number_input(prompt="EDS帧率", default_val=23))
    grab_time = resolution_w_ * resolution_h_ * dwell_time_s_ * frames_n_

    pyautogui.alert(
        text=f"1. 样品已放入、拍摄参数已调节OK、EDS探头已进入\n"
             f"2. 窗口1显示的样品位于整个待拍摄区域的左上角\n"
             f"3. EDS数据将会按照配置完成多区域采集\n"
             f"4. UI界面建议保持在Phase Maps中，以便实时展示\n"
             f"5. 根据分辨率Dwell及帧率算出每张EDS采集需要的时间为{grab_time:.1f}s\n",
             # f"6. 运行过程中按 ESC 可触发停止信号",
        title="运行前请确认如下条件已经满足",
        button="已满足可继续运行"
    )
    time.sleep(2)

    return mag_n_,interval_m_,move_cnt_w_,move_cnt_h_,resolution_w_,resolution_h_,dwell_time_s_,frames_n_


def confirm_sem_parameters(mag_n_, interval_mm_, move_cnt_w_, move_cnt_h_, res_w_, res_h_, dwell_, frames_n_):
    resp = pyautogui.confirm(
        text=f'放大倍率:{mag_n_}\n'
             f'移动间隔:{interval_mm_*1000}(mm),移动范围:{move_cnt_w_}x{move_cnt_h_}\n'
             f'EDS采集分辨率:{res_w_}x{res_h_},单像素DellTime:{dwell_*1000*1000}(us),帧率{frames_n_}\n',
        title='拍摄参数确认',
        buttons=['确认无误', '参数存在错误']
    )
    if resp == '确认无误':
        return True
    else:
        return False


def tcp_phase_analysis(pos_i_=1,mag_n_=1500.0,interval_m_=0.00009,move_cnt_w_=2,move_cnt_h_=3,res_w_=768,res_h_=512,dwell_s_=0.00002,frames_n_=23,show_statis=True,microscope_=None):
    """
    通过给定的输入参数完成move_cnt_w_*move_cnt_h_个样品区域上的TCP相的化学成分以及面积统计
    例如：对样品1500放大倍率下的2*3区域上进行TCP相的统计（没有指定的参数使用函数默认值来进行拍摄）
    :param pos_i_: 预设样品位置下标索引, 0:没有指定的预设位置从当前位置开始拍摄, -1:外部程序调起拍摄接口需要确认参数是否正确
    :param mag_n_: 放大倍数
    :param interval_m_: 样品台移动间隔(单位m 赛默飞API规定)
    :param move_cnt_w_: 横向移动次数
    :param move_cnt_h_: 纵向移动次数
    :param res_w_: EDS采集的分辨率W
    :param res_h_: EDS采集的分辨率H
    :param dwell_s_: EDS采集单个像素的时间(单位s 赛默飞API规定)
    :param frames_n_: EDS采集需要的帧数
    :param show_statis: whether need show statis
    :param microscope_: SEM client
    :return:
    """

    if pos_i_ < 0:
        if not confirm_sem_parameters(mag_n_, interval_m_, move_cnt_w_, move_cnt_h_, res_w_, res_h_, dwell_s_, frames_n_):
            logger.warning("----- Error in parameters required for TCP phase analysis -----")
            return {"status": "fail", "message": "tcp_phase_analysis's parameters are wrong"}
        microscope_ = SdbMicroscopeClient()
        microscope_.connect("localhost")
        sem_beam_switch(sem=microscope_, opt='on', logger=logger)

    sem_active_view(sem=microscope_, view_i=1, logger=logger)
    # 设置mag倍率
    sem_set_scan_params(sem=microscope_, logger=logger, mag=mag_n_, resolution=(res_w_, res_h_), dwell=None)
    if interval_m_ == 0:
        interval_m_ = microscope_.beams.electron_beam.horizontal_field_width.value
    # EDS进探头
    sem_eds_detector(sem=microscope_, logger=logger, position=EdsDetectorPositions.STANDARD_INSERTED)
    # 亮度对比度清晰度调节OK
    # 打开EDS，配置 Running Mapping中Quant、Gross和Phase均选上
    # 使用New Site来接收EDS结果（Run AutoID）
    # Preset 分辨率 Dell时间后采集
    # TODO: display analytical layout, ChemiSEM
    composition_result_list = []
    phase_statis_result_list = []
    save_dir_ = f'./output/eds_statis/{pos_i_}'
    for h_i in range(move_cnt_h_):
        for w_i in range(move_cnt_w_):
            sem_grab_scan_frame(sem=microscope_, logger=logger, resolution=(res_w_*2, res_h_*2), dwell=0.000005, save_dir=save_dir_, prefix=f'{h_i+1:03d}_{w_i+1:03d}')
            composition_result, phase_statis_result = sem_eds_phase_map(sem=microscope_, resolution=(res_w_, res_h_),
                                                                        dwell=dwell_s_, frames_n=frames_n_, component_n=3,
                                                                        logger=logger, save_dir=save_dir_, prefix=f'{h_i+1:03d}_{w_i+1:03d}')
            if composition_result:
                composition_result_list.append(composition_result)
            if phase_statis_result:
                phase_statis_result_list.append(phase_statis_result)
            if w_i < move_cnt_w_ - 1:
                sem_stage_relative(sem=microscope_, logger=logger, interval=interval_m_, x_cnt=1, y_cnt=0)
        sem_stage_relative(sem=microscope_, logger=logger, interval=interval_m_, x_cnt=-(move_cnt_w_-1), y_cnt=0)
        if h_i < move_cnt_h_ - 1:
            sem_stage_relative(sem=microscope_, logger=logger, interval=interval_m_, x_cnt=0, y_cnt=-1)
    sem_stage_relative(sem=microscope_, logger=logger, interval=interval_m_, x_cnt=0, y_cnt=move_cnt_h_-1)
    # with open("./output/debug_composition_result_list.pkl", "wb") as f:
    #     pickle.dump(composition_result_list, f)
    # with open("./output/debug_phase_statis_result_list.pkl", "wb") as f:
    #     pickle.dump(phase_statis_result_list, f)
    # with open("./output/debug_composition_result_list.pkl", "wb") as f:
    #     composition_result_list = pickle.load(f)
    # with open("./output/debug_phase_statis_result_list.pkl", "wb") as f:
    #     phase_statis_result_list = pickle.load(f)
    pretty_pandas()
    sem_statis_eds_composition(composition_result_list, logger=logger, show_statis=show_statis, need_plot=False, save_dir=save_dir_)
    sem_statis_eds_phase(phase_statis_result_list, logger=logger, show_statis=show_statis, need_plot=False, save_dir=save_dir_)

    # EDS RETRACTED探头
    # sem_eds_detector(sem=microscope_, logger=logger, position=EdsDetectorPositions.RETRACTED)
    logger.info("=====DONE====")
    if pos_i_ < 0:
        sem_beam_switch(sem=microscope_, opt='off', logger=logger)
    return {"status": "success", "message": "tcp_phase_analysis stub executed"}


if __name__ == '__main__':
    while True:
        mag_n,interval_m,move_cnt_w,move_cnt_h,res_w,res_h,dwell_s,frames_n = get_sem_parameters()
        if confirm_sem_parameters(mag_n,interval_m,move_cnt_w,move_cnt_h,res_w,res_h,dwell_s,frames_n):
            break

    logger.info("\n=====Starting TCP phase analysis and statistic script=====")
    # Connect to the AutoScript server
    logger.info("Connecting to the microscope...")
    microscope = SdbMicroscopeClient()
    microscope.connect("localhost")
    preset_positions = [(12.6452, -20.8173), (9.4126, -17.1200)]
    resp = pyautogui.confirm(
        text=f'Will move stage to:{preset_positions} (unit: mm)\n',
        title='拍摄参数确认',
        buttons=['确认无误', '参数存在错误']
    )
    if resp == '确认无误':
        pass
    else:
        exit(0)
    pos_i = 0
    sem_beam_switch(sem=microscope, opt='on', logger=logger)
    if preset_positions:
        for preset_p in preset_positions:
            pos_i += 1
            sem_stage_actual(sem=microscope, logger=logger, x_mm=preset_p[0], y_mm=preset_p[1])
            tcp_phase_analysis(pos_i,mag_n,interval_m,move_cnt_w,move_cnt_h,res_w,res_h,dwell_s,frames_n,len(preset_positions)<=1,microscope)
    else:
        tcp_phase_analysis(pos_i,mag_n,interval_m,move_cnt_w,move_cnt_h,res_w,res_h,dwell_s,frames_n,len(preset_positions)<=1,microscope)
    sem_beam_switch(sem=microscope, opt='off', logger=logger)




def foo():
    # Activate view 1
    print("Activating view 1...")
    microscope.imaging.set_active_view(1)
    print("Active view is now view %d" % microscope.imaging.get_active_view())

    # Turn electron beam on
    print("Turning electron beam on...")
    microscope.beams.electron_beam.turn_on()
    print("Beam is now %s" % ("on" if microscope.beams.electron_beam.is_on else "off"))

    # Check electron beam high voltage limits
    print("Checking electron beam high voltage limits...")
    print("High voltage limits are %s" % microscope.beams.electron_beam.high_voltage.limits)

    # Adjust electron beam high voltage
    print("Setting electron beam high voltage value to 10 kV...")
    microscope.beams.electron_beam.high_voltage.value = 10e3
    print("High voltage is now %.1f V" % microscope.beams.electron_beam.high_voltage.value)

    # Check available electron beam scanning resolutions
    print("Checking available electron beam scanning resolutions...")
    print("Available resolutions are %s" % microscope.beams.electron_beam.scanning.resolution.available_values)

    # Adjust electron beam scanning resolution
    print("Setting electron beam scanning resolution to 1536x1024...")
    microscope.beams.electron_beam.scanning.resolution.value = ScanningResolution.PRESET_1536X1024
    print("Resolution is now %s" % microscope.beams.electron_beam.scanning.resolution.value)

    # Check available detector types
    print("Checking available detector types...")
    available_detector_types = microscope.detector.type.available_values
    print("Available detectors are %s" % available_detector_types)

    # Filter available detector types to find basic ones and activate the first of them
    basic_detector_types = [d for d in available_detector_types if d in ['ETD', 'TLD', 'ICE']]
    if len(basic_detector_types) > 0:
        print("Activating %s detector..." % basic_detector_types[0])
        microscope.detector.type.value = basic_detector_types[0]
        print("Active detector is now %s" % microscope.detector.type.value)

        # Adjust active detector contrast
        print("Adjusting active detector contrast...")
        microscope.detector.contrast.value = 0.75
        print("Detector contrast is now %.2f%%" % (microscope.detector.contrast.value * 100))

    # Take one image
    print("Acquiring image with resolution 1536x1024 and dwell time 1 us...")
    settings = GrabFrameSettings(resolution="1536x1024", dwell_time=1e-6)
    image = microscope.imaging.grab_frame(settings)

    # Display the image on a pop-up window
    print("Opening a window with the acquired image... (Close it to continue)")
    plot.imshow(image.data, cmap="gray")
    plot.show()
    print("Pop-up window closed")

    print("Example script finished successfully")
