import logging
import argparse
import sys
import pylinkit
from .utils import OrderedRawConfigParser, extract_firmware_file_from_dfu, create_wrapped_file_with_crc32

erase_options = ['sensor', 'system', 'all', 'als', 'ph', 'rtd', 'cdt', 'axl', 'pressure']
dumpd_options = ['system', 'gnss', 'als', 'ph', 'rtd', 'cdt', 'axl', 'pressure', 'baro']#Tom
scalw_options = ['cdt', 'ph', 'rtd', 'mcp47x6']
resetv_options = {'tx_counter': 1, 'rx_counter': 3, 'rx_time': 4}
modulation_options = {'A2':0, 'A3': 1, 'A4': 2}


parser = argparse.ArgumentParser()
parser.add_argument('--fw', type=argparse.FileType('rb'), required=False, help='Firmware filename for FW OTA update')
parser.add_argument('--timeout', type=float, required=False, default=None, help='BLE communications timeout')
parser.add_argument('--erase', type=str, choices=erase_options, required=False, help='Erase log file')
parser.add_argument('--device', type=str, required=False, help='xx:xx:xx:xx:xx:xx BLE device address')
parser.add_argument('--parmr', type=argparse.FileType('w'), required=False, help='Filename to write [PARAM] configuration to')
parser.add_argument('--poll', type=str, required=False, help='Poll a parameter value by key and use --value to denote repetitions')
parser.add_argument('--rstvw', type=str, choices=resetv_options.keys(), required=False, help='Reset variable: tx_counter or rx_counter')
parser.add_argument('--rstbw', action='store_true', required=False, help='Reset beacon')
parser.add_argument('--factw', action='store_true', required=False, help='Factory reset (WARNING: erases all stored logs and configuration!)')
parser.add_argument('--parmw', type=argparse.FileType('r'), required=False, help='Filename to read [PARAM] configuration from')
parser.add_argument('--paspw', type=argparse.FileType('r'), required=False, help='Filename (JSON) to read pass predict configuration from')
parser.add_argument('--scan', action='store_true', required=False, help='Scan for beacons')
parser.add_argument('--debug', action='store_true', required=False, help='Turn on debug trace')
parser.add_argument('--dump_sensor', type=argparse.FileType('wb'), required=False, help='Dump sensor log file')
parser.add_argument('--dump_system', type=argparse.FileType('wb'), required=False, help='Dump system log file')
parser.add_argument('--dumpd', type=argparse.FileType('wb'), required=False, help='Dump the specified log file')
parser.add_argument('--dumpd_type', type=str, choices=dumpd_options, required=False, help='Specified log file')
parser.add_argument('--gui', action='store_true', required=False, help='Launch in GUI mode')
parser.add_argument('--argostx', action='store_true', required=False, help='Send argos TX packet')
parser.add_argument('--argosmod', type=str, default='A2', required=False, help='Argos modulation (A2, A3)')
parser.add_argument('--argosfreq', type=float, default=401.65, required=False, help='Argos frequency in MHz')
parser.add_argument('--argossize', type=int, default=15, required=False, help='Packet size in bytes')
parser.add_argument('--argostcxo', type=int, default=5, required=False, help='TCXO warm-up in seconds')
parser.add_argument('--argospower', type=int, default=350, required=False, help='TX power in mW')
parser.add_argument('--scalw', type=str, choices=scalw_options, required=False, help='Run a calibration command')
parser.add_argument('--command', type=int, required=False, help='Calibration command number')
parser.add_argument('--value', type=float, default=0, required=False, help='Calibration command value')
parser.add_argument('--ano', type=argparse.FileType('rb'), required=False, help='GNSS AssistNow Offline filename')
args = parser.parse_args()


def setup_logging(enabled, level):
    if enabled:
        logging.basicConfig(format='%(asctime)s\t%(module)s\t%(levelname)s\t%(message)s', level=logging.ERROR)
        if level == 'error':
            logging.getLogger().setLevel(logging.ERROR)
        elif level == 'warn':
            logging.getLogger().setLevel(logging.WARN)
        elif level == 'info':
            logging.getLogger().setLevel(logging.INFO)
        elif level == 'debug':
            logging.getLogger().setLevel(logging.DEBUG)


def gui_main():
    from .gui import run
    run()


def main():
    if not any(vars(args).values()):
        parser.print_help()
        sys.exit(2)

    if args.debug:
        setup_logging(True, 'debug')
    else:
        setup_logging(True, 'info')

    if args.gui:
        gui_main()

    dev = None
    if args.device:
        dev = pylinkit.Tracker(args.device)

    if args.parmr:
        dev.sync()
        d = {}
        d['PARAM'] = dev.get()
        cfg = OrderedRawConfigParser()
        cfg.optionxform = lambda option: option
        cfg.read_dict(dictionary=d)
        cfg.write(args.parmr)
        args.parmr.close()

    if args.poll and args.value is not None:
        dev.poll(args.poll, int(args.value))

    if args.parmw:
        cfg = OrderedRawConfigParser()
        cfg.optionxform = lambda option: option
        cfg.read_string(args.parmw.read())
        dev.set(cfg['PARAM'])

    if args.paspw:
        dev.paspw(args.paspw.read())

    if args.dump_sensor:
        args.dump_sensor.write(dev.dumpd('sensor'))
        args.dump_sensor.close()

    if args.dump_system:
        args.dump_system.write(dev.dumpd('system'))
        args.dump_system.close()

    if args.dumpd and args.dumpd_type:
        args.dumpd.write(dev.dumpd(args.dumpd_type))
        args.dumpd.close()

    if args.erase:
        dev.erase(args.erase)

    if args.fw:
        if (args.fw.name.endswith('.zip')):
            dev.firmware_update(extract_firmware_file_from_dfu(args.fw), 0, args.timeout)
        else:
            dev.firmware_update(args.fw.read(), 0, args.timeout)

    if args.ano:
        dev.firmware_update(create_wrapped_file_with_crc32(args.ano.read()), 2, args.timeout)

    if args.factw:
        dev.factw()

    if args.rstvw:
        dev.rstvw(resetv_options[args.rstvw])

    if args.rstbw:
        dev.rstbw()

    if args.scalw:
        if args.command is None:
            print("""
            Calibration requires a command.  Use --command to provide a command:

            cdt::

            --scalw cdt --command 0 ; to reset existing CDT calibration
            --scalw cdt --command 1 --value 200000 ; to measure and compute gain factor for 200K
            --scalw cdt --command 2 --value xxxx ; to override CA polynomial coefficient
            --scalw cdt --command 3 --value xxxx ; to override CB polynomial coefficient
            --scalw cdt --command 4 --value xxxx ; to override CC polynomial coefficient
            --scalw cdt --command 5 ; to save all CDT calibration values to filesystem

            ph::

            --scalw ph --command 0 ; reset PH calibration
            --scalw ph --command 1 ; perform PH 7 (Mid) calibration
            --scalw ph --command 2 ; perform PH 1 (Low) calibration
            --scalw ph --command 3 ; perform PH 14 (High) calibration

            rtd::

            --scalw rtd --command 0 ; reset RTD calibration, wakeup device
            --scalw rtd --command 1 ; perform 0C calibration
            --scalw rtd --command 2 ; perform 100C calibration
            --scalw rtd --command 3 ; put device back into sleep mode

            mcp47x6::

            --scalw mcp47x6 --command 0 ; reset mcp47x6 calibration
            --scalw mcp47x6 --command 350 --value 2345 ; calibration point for DAC for 350 mW power
            --scalw mcp47x6 --command 500 --value 2645 ; calibration point for DAC for 500 mW power
            --scalw mcp47x6 --command 1 ; save mcp47x6 calibration to file

            Note: use in conjunction with --argostx to send a packet at calibrated mW

            """)
            return
        dev.scalw(args.scalw, args.command, args.value)

    if args.argostx:
        dev.argostx(args.argosmod, args.argospower, args.argosfreq, args.argossize, args.argostcxo)

    if args.scan:
        scan_dev = pylinkit.Scanner()
        result = scan_dev.scan()
        for x in result:
            print(x.address, x.name)


if __name__ == "__main__":
    main()
