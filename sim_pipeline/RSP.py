import numpy as np
import matplotlib.pyplot as plt
import mpl_toolkits.axisartist.floating_axes as floating_axes
from mpl_toolkits.axisartist.grid_finder import (FixedLocator, MaxNLocator,
                                                 DictFormatter)
from matplotlib.transforms import Affine2D
import pickle
import lsst.daf.butler as dafButler
import lsst.geom as geom
# Source injection
from lsst.pipe.tasks.insertFakes import _add_fake_sources
from sim_pipeline.image_simulation import gsobj_true_flux
import galsim
from astropy.io import fits
from astropy.table import Table
from sim_pipeline.image_simulation import sharp_image

def DC2_cutout(ra, dec, num_pix, butler, band):
    """
    :param ra: ra for the cutout
    :param dec: dec for the cutout
    :param num_pix: number of pixel for the cutout
    :param delta_pix: pixel scale for the lens image
    :param butler: butler object
    :param: band: image band
    :returns: cutout images
    """
    skymap = butler.get("skyMap")
    point = geom.SpherePoint(ra, dec, geom.degrees)
    cutoutSize = geom.ExtentI(num_pix, num_pix)
    #print(cutoutSize)


    #Read this from the table we have at hand... 
    tractInfo = skymap.findTract(point)
    patchInfo = tractInfo.findPatch(point)
    my_tract = tractInfo.tract_id
    my_patch = patchInfo.getSequentialIndex()
    xy = geom.PointI(tractInfo.getWcs().skyToPixel(point))
    bbox = geom.BoxI(xy - cutoutSize//2, cutoutSize)
    coaddId_r = {
        'tract':my_tract, 
        'patch':my_patch,
        'band': band
    }
    coadd_cut_r = butler.get("deepCoadd", parameters={'bbox':bbox}, dataId=coaddId_r)
    return coadd_cut_r
    
def lens_inejection(lens_pop, ra, dec, num_pix, delta_pix, butler, flux=None):
    """
    :param sim_lens: lens image
    :param ra: ra for the cutout
    :param dec: dec for the cutout
    :param num_pix: number of pixel for the cutout
    :param delta_pix: pixel scale for the lens image
    :param butler: butler object
    :param flux: flux need to be asigned to the lens image. It sould be None
    :param: path: path to save the output
    :returns: cutout images with injected lens
    """   
    #lens = sim_lens
    kwargs_lens_cut={'min_image_separation': 0.8, 'max_image_separation': 10, 'mag_arc_limit': {'g': 23, 'r': 23, 'i': 23}}
    rgb_band_list=['r', 'g', 'i']
    lens_class = lens_pop.select_lens_at_random(**kwargs_lens_cut)
    theta_E=lens_class.einstein_radius
    #lens=sharp_image(lens_class=lens_class, band='i', mag_zero_point=27, delta_pix=delta_pix, num_pix=num_pix)
    skymap = butler.get("skyMap")
    point = geom.SpherePoint(ra, dec, geom.degrees)
    cutoutSize = geom.ExtentI(num_pix, num_pix)
    #Read this from the table we have at hand 
    tractInfo = skymap.findTract(point)
    patchInfo = tractInfo.findPatch(point)
    my_tract = tractInfo.tract_id
    my_patch = patchInfo.getSequentialIndex()
    xy = geom.PointI(tractInfo.getWcs().skyToPixel(point))
    bbox = geom.BoxI(xy + cutoutSize//2, cutoutSize)
    injected_final_image = []
    band_report = []
    box_center = []
    for band in rgb_band_list:
        coaddId_r = {
            'tract':my_tract, 
            'patch':my_patch,
            'band': band
        }
        
        #coadd cutout image
        coadd_cut_r = butler.get("deepCoadd", parameters={'bbox':bbox}, dataId=coaddId_r)
        lens=sharp_image(lens_class=lens_class, band=band, mag_zero_point=27, delta_pix=delta_pix, num_pix=num_pix)
        if flux == None:
            gsobj = gsobj_true_flux(lens, pix_scale=delta_pix)
        else:
            gsobj = galsim.InterpolatedImage(galsim.Image(lens), scale = delta_pix, flux = flux)

        wcs_r= coadd_cut_r.getWcs()
        bbox_r= coadd_cut_r.getBBox()
        x_min_r = bbox_r.getMinX()
        y_min_r = bbox_r.getMinY()
        x_max_r = bbox_r.getMaxX()
        y_max_r = bbox_r.getMaxY()

        # Calculate the center coordinates
        x_center_r = (x_min_r + x_max_r) / 2
        y_center_r = (y_min_r + y_max_r) / 2

        center_r = geom.Point2D(x_center_r, y_center_r)
        #geom.Point2D(26679, 15614)
        point_r=wcs_r.pixelToSky(center_r)
        ra_degrees = point_r.getRa().asDegrees()
        dec_degrees = point_r.getDec().asDegrees()
        center =(ra_degrees, dec_degrees)

        image_r = butler.get("deepCoadd", parameters={'bbox':bbox_r}, dataId=coaddId_r)
        mat = np.eye(3)
        mat[:2,:2] = wcs_r.getCdMatrix()

        transform = Affine2D(mat)
        #arr_r = np.copy(image_r.image.array)

        _add_fake_sources(image_r, [(point_r, gsobj)])
        inj_arr_r = image_r.image.array
        injected_final_image.append(inj_arr_r)
        band_report.append(band)
        box_center.append(center)

    t = Table([injected_final_image, band_report, box_center], names=('lens', 'band', 'cutout_center'))
    return t
    