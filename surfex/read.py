import os
import surfex
from surfex.util import data_merge
import copy
from abc import abstractmethod, ABCMeta
import numpy as np
try:
    from StringIO import StringIO   # Python 2.x
except ImportError:
    from io import StringIO         # Python 3.x


class ReadData(object):
    __metaclass__ = ABCMeta

    def __init__(self, geo, var_name):
        self.geo = geo
        self.var_name = var_name
        # print "Constructed "+self.__class__.__name__+" for " + self.var_name

    @abstractmethod
    def read_time_step(self, validtime, cache):
        raise NotImplementedError('users must define read_time_step to use this base class')

    @abstractmethod
    def print_info(self):
        raise NotImplementedError('users must define read_time_step to use this base class')


# Direct data can be ead with this class with converter = None
class ConvertedInput(ReadData):

    def __init__(self, geo, var_name, converter):
        ReadData.__init__(self, geo, var_name)
        self.converter = converter

    def read_time_step(self, validtime, cache):
        field = self.converter.read_time_step(self.geo, validtime, cache)
        # Preserve positive values for precipitation
        # TODO
        # if self.var_name == "RAIN" or self.var_name == "SNOW":
        #    field[field < 0.] = 0.
        return field

    def print_info(self):
        self.converter.print_info()


class ConstantValue(ReadData):

    def __init__(self, geo, var_name, var_dict):
        ReadData.__init__(self, geo, var_name)
        self.var_dict = var_dict
        if "value" in self.var_dict:
            self.value = self.var_dict["value"]
        else:
            print("Constant value must have a value!")
            raise

    def read_time_step(self, validtime, cache):
        field = np.array([float(i) for i in range(0, self.geo.npoints)])
        field.fill(self.value)
        # print field.shape
        return field

    def print_info(self):
        print(self.var_name)


def remove_existing_file(f_in, f_out):
    if f_in is None:
        raise FileNotFoundError("Input file not set")
    # If files are not the same file
    if os.path.abspath(f_in) != os.path.abspath(f_out):
        if os.path.isdir(f_out):
            raise IsADirectoryError(f_out + " is a directory! Please remove it if desired")
        if os.path.islink(f_out):
            os.unlink(f_out)
        if os.path.isfile(f_out):
            os.remove(f_out)
    # files have the same path. Remove if it is a symlink
    else:
        if os.path.islink(f_out):
            os.unlink(f_out)


#######################################################
#######################################################


class Converter:
    """
    Main interface to read a field is done through a converter
    The converter is default "None" to read a plain field
    """

    def __init__(self, name, validtime, defs, conf, fileformat, basetime, debug=False):
        """
        Initializing the converter

        :param name: name
        :param conf: dictionary
        :param fileformat: format
        """

        self.name = name
        self.validtime = validtime
        self.basetime = basetime
        # self.intervall = intervall

        if self.name not in conf:
            print(conf)
            raise KeyError(self.name + " is missing in converter definition")

        if self.name == "none":
            self.var = self.create_variable(fileformat, defs, conf[self.name], debug)
        elif name == "rh2q":
            self.rh = self.create_variable(fileformat, defs, conf[self.name]["rh"], debug)
            self.t = self.create_variable(fileformat, defs, conf[self.name]["t"], debug)
            self.p = self.create_variable(fileformat, defs, conf[self.name]["p"], debug)
        elif name == "windspeed" or name == "winddir":
            self.x = self.create_variable(fileformat, defs, conf[self.name]["x"], debug)
            self.y = self.create_variable(fileformat, defs, conf[self.name]["y"], debug, need_alpha=True)
        elif name == "totalprec":
            self.totalprec = self.create_variable(fileformat, defs, conf[self.name]["totalprec"], debug)
            self.snow = self.create_variable(fileformat, defs, conf[self.name]["snow"], debug)
        elif name == "calcsnow":
            self.totalprec = self.create_variable(fileformat, defs, conf[self.name]["totalprec"], debug)
            self.t = self.create_variable(fileformat, defs, conf[self.name]["t"], debug)
        #            self.rh = self.create_variable(fileformat,defs,conf[self.name]["t"],debug)
        #            self.p = self.create_variable(fileformat,defs,conf[self.name]["p"],debug)
        elif name == "calcrain":
            self.totalprec = self.create_variable(fileformat, defs, conf[self.name]["totalprec"], debug)
            self.t = self.create_variable(fileformat, defs, conf[self.name]["t"], debug)
        elif name == "phi2m":
            self.phi = self.create_variable(fileformat, defs, conf[self.name]["phi"], debug)
        else:
            print("Converter " + self.name + " not implemented")
            raise NotImplementedError

        # print "Constructed the converter " + self.name

    def print_info(self):
        print(self.name)

    def create_variable(self, fileformat, defs, var_dict, debug, need_alpha=False):

        # Finally we can merge the variable with the default settings
        # Create deep copies not to inherit between variables
        defs = copy.deepcopy(defs)
        var_dict = copy.deepcopy(var_dict)
        merged_dict = data_merge(defs, var_dict)

        print(fileformat)
        if fileformat == "netcdf":
            var = surfex.variable.NetcdfVariable(merged_dict, self.basetime, self.validtime,  debug=debug,
                                                 need_alpha=need_alpha)
        elif fileformat == "grib":
            var = surfex.variable.GribVariable(merged_dict, self.basetime, self.validtime,  debug=debug,
                                               need_alpha=need_alpha)
        elif fileformat == "surfex":
            var = surfex.variable.SurfexVariable(merged_dict, self.basetime, self.validtime, debug=debug,
                                                 need_alpha=need_alpha)
        elif fileformat == "constant":
            raise NotImplementedError("Create variable for format " + fileformat + " not implemented!")
        else:
            raise NotImplementedError("Create variable for format " + fileformat + " not implemented!")

        # TODO: Put this under verbose flag and format printing
        # var.print_variable_info()
        return var

    def read_time_step(self, geo, validtime, cache):
        # print("Time in converter: "+self.name+" "+validtime.strftime('%Y%m%d%H'))

        gravity = 9.81
        field = np.empty(geo.npoints)
        # Specific reading for each converter
        if self.name == "none":
            field = self.var.read_variable(geo, validtime, cache)
        elif self.name == "windspeed" or self.name == "winddir":
            field_x = self.x.read_variable(geo, validtime, cache)
            alpha, field_y = self.y.read_variable(geo, validtime, cache)
            # field_y = self.y.read_variable(geo,validtime,cache)
            if self.name == "windspeed":
                field = np.sqrt(np.square(field_x) + np.square(field_y))
                np.where(field < 0.005, field, 0)
            elif self.name == "winddir":
                field = np.mod(np.rad2deg(np.arctan2(field_x, field_y)) + 180 - alpha, 360)

        elif self.name == "rh2q":
            field_rh = self.rh.read_variable(geo, validtime, cache)  # %
            field_t = self.t.read_variable(geo, validtime, cache)  # In K
            field_p = self.p.read_variable(geo, validtime, cache)  # In Pa

            field_p_mb = np.divide(field_p, 100.)
            field_t_c = np.subtract(field_t, 273.15)

            exp = np.divide(np.multiply(17.67, field_t_c), np.add(field_t_c, 243.5))
            es = np.multiply(6.112, np.exp(exp))
            field = np.divide(np.multiply(0.622, field_rh / 100.) * es, field_p_mb)

            # ZES = 6.112 * exp((17.67 * (ZT - 273.15)) / ((ZT - 273.15) + 243.5))
            # ZE = ZRH * ZES
            # ZRATIO = 0.622 * ZE / (ZPRES / 100.)
            # RH2Q = 1. / (1. / ZRATIO + 1.)
        elif self.name == "totalprec":
            field_totalprec = self.totalprec.read_variable(geo, validtime, cache)
            field_snow = self.snow.read_variable(geo, validtime, cache)
            field = np.subtract(field_totalprec, field_snow)
        elif self.name == "calcrain":
            field_totalprec = self.totalprec.read_variable(geo, validtime, cache)
            field_t = self.t.read_variable(geo, validtime, cache)
            field = field_totalprec
            field[field_t < 1] = 0
        elif self.name == "calcsnow":
            field_totalprec = self.totalprec.read_variable(geo, validtime, cache)
            # field_rh = self.rh.read_variable(geo, validtime,cache) #
            field_t = self.t.read_variable(geo, validtime, cache)  # In K
            # field_p = self.p.read_variable(geo, validtime,cache)   # In Pa
            # tc = field_t + 273.15
            # e  = (field_rh)*0.611*exp((17.63*tc)/(tc+243.04));
            # Td = (116.9 + 243.04*log(e))/(16.78-log(e));
            # gamma = 0.00066 * field_p/1000;
            # delta = (4098*e)/pow(Td+243.04,2);
            # if(gamma + delta == 0):
            # print("problem?")
            # wetbulbTemperature = (gamma * tc + delta * Td)/(gamma + delta);
            # wetbulbTemperatureK  = wetbulbTemperature + 273.15;
            field = field_totalprec
            field[field_t > 1] = 0
        elif self.name == "phi2m":
            field = self.phi.read_variable(geo, validtime, cache)
            field = np.divide(field, gravity)
            field[(field < 0)] = 0.
        else:
            print("Converter " + self.name + " not implemented")
            raise NotImplementedError
        return field


def read_surfex_field(varname, filename, validtime, patch=-1, layer=-1, accumulated=False, fileformat=None,
                      filetype=None, debug=False, geo=None):

    if fileformat is None:
        fileformat, filetype = surfex.file.guess_file_format(filename, filetype)

    if filetype == "surf":
        if fileformat.lower() == "ascii":
            geo = surfex.file.AsciiSurfexFile(filename).geo
        elif fileformat.lower() == "nc":
            geo = surfex.file.NCSurfexFile(filename).geo
        else:
            if geo is None:
                raise NotImplementedError("Not implemnted and geo is None")
    elif geo is None:
        raise Exception("You need to provide a geo object. Filetype is: " + str(filetype))

    var_dict = {
        "none": {
            "varname": varname,
            "patches": patch,
            "layers": layer,
            "fileformat": fileformat,
            "filetype": filetype,
            "filepattern": filename,
            "accumulated": accumulated,
            "file_inc": 6,
            "offset": 0,
            "fcint": 3
        }
    }
    cache = surfex.cache.Cache(debug, 3600)

    # name, validtime, defs, conf, fileformat, basetime,  debug):
    converter = Converter("none", validtime, {}, var_dict, "surfex", validtime, debug=debug)
    field = ConvertedInput(geo, varname, converter).read_time_step(validtime, cache)
    return field