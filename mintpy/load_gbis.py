#!/usr/bin/env python3
############################################################
# Program is part of MintPy                                #
# Copyright(c) 2019, Zhang Yunjun                          #
# Author:  Zhang Yunjun                                    #
############################################################


import os
import argparse
import numpy as np
import scipy.io as sio
import matplotlib.pyplot as plt
import pyproj
from mintpy.utils import writefile


EXAMPLE = """example:
  load_gbis.py invert_1_2_C.mat
"""

def create_parser():
    parser = argparse.ArgumentParser(description='Load GBIS inversion result to HDF5 format.',
                                     formatter_class=argparse.RawTextHelpFormatter,
                                     epilog=EXAMPLE)

    parser.add_argument('file', help='GBIS inversion mat file.')
    parser.add_argument('-o', '--output', dest='outfile', help='output file name.')
    parser.add_argument('--nodisplay', dest='disp_fig', action='store_false', help='do not display the figure')
    return parser


def cmd_line_parse(iargs=None):
    parser = create_parser()
    inps = parser.parse_args(args=iargs)
    inps.file = os.path.abspath(inps.file)
    return inps


def gbis_mat2hdf5(mat_file, display=True):
    """Convert InSAR related GBIS inversion result .mat file into HDF5 file."""
    out_dir = os.path.dirname(mat_file)
    out_files = []

    print('read mat file: {}'.format(mat_file))
    mat = sio.loadmat(mat_file, struct_as_record=False, squeeze_me=True)
    num_file = len(mat['insar'])
    print('number of output HDF5 file: {}'.format(num_file))

    # grab optimal model parameter
    parValue = mat['invResults'].optimalmodel
    parName = mat['invResults'].model.parName
    mDict = {}
    for i in range(len(parValue)):
        key = parName[i].replace(' ', '_')
        mDict[key] = parValue[i]

    # convert model x/y to lat/lon
    ref_lon, ref_lat = mat['geo'].referencePoint
    geod = pyproj.Geod(ellps='WGS84')
    mX, mY = parValue[0:2]
    mLon, mLat = geod.fwd(ref_lon, ref_lat,
                          az=np.arctan(mX/mY) * 180 / np.pi,
                          dist=(mX**2 + mY**2)**0.5,
                          radians=False)[0:2]
    modelName = parName[0].split()[0]
    mDict['{}_latitude'.format(modelName)] = mLat
    mDict['{}_longitude'.format(modelName)] = mLon

    if display:
        fig_size = [12, 3*num_file]
        fig, axs = plt.subplots(nrows=num_file, ncols=3, figsize=fig_size)
        print('creating figure in size of {}'.format(fig_size))

    for i in range(num_file):
        data_file = mat['insar'][i].dataPath
        print('-'*30)
        print('read mask from file: {}'.format(data_file))

        # read mask
        mask = sio.loadmat(data_file, struct_as_record=False, squeeze_me=True)['Mask']
        length, width = mask.shape

        # convert to 2D matrix
        insarPlot = mat['insarPlot'][i]
        out_file = os.path.join(out_dir, '{}.h5'.format(insarPlot.name))
        out_files.append(out_file)

        data = np.zeros((length, width), dtype=np.float32) * np.nan
        model = np.zeros((length, width), dtype=np.float32) * np.nan
        residual = np.zeros((length, width), dtype=np.float32) * np.nan
        data[mask!=0] = insarPlot.data
        model[mask!=0] = insarPlot.model
        residual[mask!=0] = insarPlot.residual

        # prepare metadata
        meta = vars(sio.loadmat(data_file, struct_as_record=False, squeeze_me=True)['Metadata'])
        temp = meta.pop('_fieldnames') # remote _fieldnames added by Matlab
        meta['UNIT'] = 'm'
        meta['FILE_TYPE'] = 'displacement'
        meta['PROCESSOR'] = 'isce'
        if 'minHeight' in vars(insarPlot).keys():
            meta['MODEL_MIN_HEIGHT'] = insarPlot.minHeight
        for key, value in mDict.items():
            meta[key] = value

        # write to HDF5 file
        dsDict = {}
        dsDict['data'] = data
        dsDict['model'] = model
        dsDict['residual'] = residual
        writefile.write(dsDict, out_file=out_file, metadata=meta)

        # plot
        if display:
            dlim = np.nanmax(np.abs(data))
            for ax, d in zip(axs[i, :], [data, model, residual]):
                im = ax.imshow(d, vmin=-dlim, vmax=dlim, cmap='jet')
                fig.colorbar(im, ax=ax)
            axs[i,0].set_ylabel('\n'.join(insarPlot.name.split('_', 1)))

    if display:
        print('showing ...')
        axs[0,0].set_title('data')
        axs[0,1].set_title('model')
        axs[0,2].set_title('residual')
        plt.show()
    return out_files


##############################################################################
def main(iargs=None):
    inps = cmd_line_parse(iargs)

    out_files = gbis_mat2hdf5(inps.file, display=inps.disp_fig)

    return out_files


##########################################################################
if __name__ == '__main__':
    main()
