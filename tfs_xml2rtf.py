#!/usr/bin/env python

import xml.etree.ElementTree as ET
import argparse
import os
import shutil
import subprocess
import glob
import inspect
import tqdm
import math

USAGE="""
Navigates directory tree and extracts selected information from EPU XML file series.

USAGE:
  %s <epu_project_directory> <options>

""" % ((__file__,)*1)

MODIFIED="Modified 2025 May 07"
MAX_VERBOSITY=4

def printvars(variables, quitTF=False, typeTF=False):
    """Print the local variables in the caller's frame.

    Adapted from https://stackoverflow.com/questions/6618795/get-locals-from-calling-namespace-in-python
    """

    if type(variables) is list:
        # Weird things happen if
        assert isinstance(variables[0], str), "UH OH!! Passed non-string %s instead of variable name" % variables[0]

        variable_list= variables
    elif isinstance(variables, str):
        variable_list= [variables]
    else:
        print("ERROR!! Don't know how to deal with type %s" % type(variables) )
        exit()

    frame = inspect.currentframe()
    dictionary= frame.f_back.f_locals

    print("")
    for variable in variable_list :
        try:
          msg= "%s: '%s'" % (variable, dictionary[variable])
        except KeyError as e:
          print(f"Can't find key '{variable}'")
          print(f"dictionary: '{dictionary.keys()}'")
          print("Exiting...")
          exit()

        if typeTF: msg+= " %s" % type(dictionary[variable])
        print(msg)

    del frame

    if quitTF:
        print('\nExiting printvars...')  # reminder in case I forget to take out the quit flag
        exit()

def main(options):
  verbosity= options.verbosity
  xml_list= []
  if options.progress and verbosity!=2: verbosity=1
  if verbosity==1 or verbosity==2: options.progress=True

  if verbosity>=1:
    print()
    print(f"{os.path.basename(__file__)}, {MODIFIED}")
    print(f"  Top-level directory: {options.directory}")
    print(f"  Output filename: {options.output}")
    print(f"  Skip movie scan? {options.no_scan}")
    print(f"  Show progress bar? {options.progress}")
    print(f"  Verbosity level: {verbosity}")
    print()

  if verbosity>=1: print("Navigating top-level directory...")
  dir_list= [x[0] for x in os.walk(options.directory) if os.path.basename(x[0]) == 'Data']
  if verbosity>=1: print("Finished navigating directory\n")

  # Loop through directories
  for curr_dir in dir_list:
    rel_path= os.path.relpath(curr_dir, start=options.directory)

    # "Data" directories will be three directories down from top-level project directory
    rel_depth= len( rel_path.split('/') )

    if verbosity>=2:
      printvars(['rel_path', 'curr_dir', 'rel_depth'])

    # Search for XML files
    ###if rel_depth==2:  # SHOULDN'T NEED TO CHECK DEPTH IF DIRECTORY IS CALLED 'Data'
    dir_xmls= glob.glob( os.path.join(curr_dir, 'Foil*.xml') )
    xml_list+= dir_xmls
    if verbosity>=2:
      print(f"num_xmls: {len(dir_xmls)}")
  # End directory loop

  if len(xml_list) == 0:
    print(f"\nERROR!! Found 0 XML files in {len(dir_list)} directories!")
    print("  Exiting...\n")
    exit()
  else:
    if verbosity>=2: print()
    if verbosity>=1:
      print(f"Found {len(xml_list)} XML files in {len(dir_list)} directories")
      if not options.no_scan:
        print("Scanning first 2 movies for number of frames...")
      else:
        print("Not scanning movies for number of frames...")
      print()

  # Initialize
  min_df=+999.9
  max_df=-999.9
  num_frames= None
  movie_format= None
  min_tilt=+360.0
  max_tilt=-360.0

  do_disable= verbosity!=1 or options.debug

  # Loop through XML files
  for xml_idx in tqdm.tqdm(range( len(xml_list) ), unit='xml', disable=do_disable):
    curr_xml= xml_list[xml_idx]
    if verbosity>=4:
      print(f"XML file:\t\t\t\t {curr_xml}")
    elif verbosity>=3:
      print(f"XML file[{xml_idx+1}]: {curr_xml}")

    tree = ET.parse(curr_xml)
    root=tree.getroot()

    # Find the relevant elements using the namespace
    namespace_shared_dict = {'a': 'http://schemas.datacontract.org/2004/07/Fei.SharedObjects'}
    namespace_shared_str = "{" + namespace_shared_dict['a'] + "}"
    namespace_array_dict = {'a': 'http://schemas.microsoft.com/2003/10/Serialization/Arrays'}

    # InstrumentModel
    scope_text= find_simple_tag(root, "InstrumentModel", namespace_shared_dict, pad='\t\t\t' if verbosity>=4 else '')

    # Krios name starts with TITAN####
    if scope_text.startswith("TITAN"):
      scope_title= "Krios"
    else:
      scope_title= scope_text.split('-')[0].title()

    # DetectorCommercialName
    cam_text= find_complex_tag(root, "DetectorCommercialName", namespace_array_dict, parent_key='KeyValueOfstringanyType', pad='\t\t' if verbosity>=4 else '')

    # Counting
    count_text= find_complex_tag(root, "ElectronCountingEnabled", namespace_array_dict, parent_key='KeyValueOfstringanyType', pad='\t\t' if verbosity>=4 else '')

    # Voltage
    volt_text= find_simple_tag(root, "AccelerationVoltage", namespace_shared_dict, pad='\t\t\t' if verbosity>=4 else '')

    # Software version
    sw_text= find_simple_tag(root, "ApplicationSoftware", namespace_shared_dict, pad='\t\t\t' if verbosity>=4 else '')
    version_text= find_simple_tag(root, "ApplicationSoftwareVersion", namespace_shared_dict, pad='\t\t' if verbosity>=4 else '')

    # Apertures
    c1_text= find_complex_tag(root, "Aperture[C1].Name", namespace_array_dict, parent_key='KeyValueOfstringanyType', pad='\t\t\t' if verbosity>=4 else '')
    c2_text= find_complex_tag(root, "Aperture[C2].Name", namespace_array_dict, parent_key='KeyValueOfstringanyType', pad='\t\t\t' if verbosity>=4 else '')
    c3_text= find_complex_tag(root, "Aperture[C3].Name", namespace_array_dict, parent_key='KeyValueOfstringanyType', pad='\t\t\t' if verbosity>=4 else '')
    obj_aperture= find_complex_tag(root, "Aperture[OBJ].Name", namespace_array_dict, parent_key='KeyValueOfstringanyType', pad='\t\t\t' if verbosity>=4 else '')
    #printvars('obj_aperture',True)

    # optics -> SpotIndex
    spot_text= find_simple_tag(root, "SpotIndex", namespace_shared_dict, pad='\t\t\t\t' if verbosity>=4 else '')

    # TemMagnification -> NominalMagnification
    mag_text= find_simple_tag(root, "NominalMagnification", namespace_shared_dict, pad='\t\t\t' if verbosity>=4 else '')

    # SpatialScale -> pixelSize -> {x,y} -> numericValue
    apix_element= find_element(root, "pixelSize", namespace_shared_dict, prefix='  ')
    apix_x_element= find_element(apix_element, "x", namespace_shared_dict)
    apix_x_text= find_simple_tag(apix_x_element, "numericValue", namespace_shared_dict, pad='\t\t\t' if verbosity>=4 else '', prefix='x')
    apix_y_element= find_element(apix_element, "y", namespace_shared_dict)
    apix_y_text= find_simple_tag(apix_y_element, "numericValue", namespace_shared_dict, pad='\t\t\t' if verbosity>=4 else '', prefix='y')
    assert apix_x_text==apix_y_text, f"UH OH!! Pixel size in x ({apix_x_text}) doesn't equal in y ({apix_y_text})!"

    # Position -> A (tilt angle)
    position_element= find_element(root, "Position", namespace_shared_dict, prefix='  ')
    tilt_radians= find_simple_tag(position_element, "A", namespace_shared_dict, pad='\t\t\t\t\t' if verbosity>=4 else '')
    tilt_degrees= round(math.degrees( float(tilt_radians) ),1)

    # Check against extrema
    if min_tilt > tilt_degrees : min_tilt=tilt_degrees
    if max_tilt < tilt_degrees : max_tilt=tilt_degrees

    # AppliedDefocus
    df_text= find_complex_tag(root, "AppliedDefocus", namespace_array_dict, parent_key='KeyValueOfstringanyType', pad='\t\t\t' if verbosity>=4 else '')

    # Check against defocus extrema
    df_microns= float(df_text)*1e+6
    if -min_df < -df_microns : min_df=df_microns
    if -max_df > -df_microns : max_df=df_microns

    # Detectors[EF-Falcon].TotalDose (UNITS?)
    f4_dose_text= find_complex_tag(root, "Detectors[EF-Falcon].TotalDose", namespace_array_dict, parent_key='KeyValueOfstringanyType', pad='\t' if verbosity>=4 else '')

    # Dose (UNITS?)
    custom_dose_text= find_complex_tag(root, "Dose", namespace_array_dict, parent_key='KeyValueOfstringanyType', pad='\t\t\t\t\t' if verbosity>=4 else '')

    # EnergySelectionSlitWidth
    slit_text= find_simple_tag(root, "EnergySelectionSlitWidth", namespace_shared_dict, pad='\t\t' if verbosity>=4 else '')

    # Detectors[EF-Falcon].ExposureTime
    custom_element= find_element(root, "CustomData", namespace_shared_dict)
    f4_exp_text= find_complex_tag(custom_element, "Detectors[EF-Falcon].ExposureTime", namespace_array_dict, parent_key='KeyValueOfstringanyType', pad='\t' if verbosity>=4 else '')

    # microscopeData -> acquisition -> camera -> ExposureTime
    camera_element= find_element(root, "camera", namespace_shared_dict)
    cam_exp_text= find_simple_tag(camera_element, "ExposureTime", namespace_shared_dict, pad='\t\t\t\t' if verbosity>=4 else '')

    # Sanity check: Make sure the two exposure times are equal to 2 decimal places
    assert round( float(f4_exp_text), 2) == round(float(cam_exp_text), 2), f"UH OH!! Exposure time in 'Detectors[EF-Falcon].ExposureTime' ({f4_exp_text}) doesn't equal 'microscopeData -> acquisition -> camera -> ExposureTime' ({cam_exp_text})!"
    #printvars(['f4_exp_text','cam_exp_text'], True)

    # Detectors[EF-Falcon].FrameRate
    frames_text= find_complex_tag(root, "Detectors[EF-Falcon].FrameRate", namespace_array_dict, parent_key='KeyValueOfstringanyType', pad='\t' if verbosity>=4 else '')

    # Movies might be either EER or TIFF format, try both
    if not options.no_scan:
      # read the number of frames for the first two movies
      if xml_idx<2:
        # EER file is assumed to be the XML prefix + "_EER.eer"
        eer_file= os.path.splitext(curr_xml)[0] + "_EER.eer"
        if os.path.exists(eer_file):
          movie_format= "eer"
          if verbosity>=4: print(f"  EerFile\t\t\t\t {eer_file}")
          if options.debug: print(f"  Checking number of frames for '{eer_file}'")
          num_frames= check_frames(eer_file, debug=False)
          if options.debug: print(f"  Number of frames: {num_frames}")

          if verbosity>=4:
            print(f"  NumberOfFrames\t\t\t {num_frames}")
            print()

        # Try TIFF
        else:
          movie_format= "tiff"
          tiff_file= os.path.splitext(curr_xml)[0] + "_Fractions.tiff"
          if os.path.exists(tiff_file):
            if verbosity>=4: print(f"  TiffFile\t\t\t\t {tiff_file}")
            if options.debug: print(f"  Checking number of frames for '{tiff_file}'")
            num_frames= check_frames(tiff_file, debug=False)
            if options.debug: print(f"  Number of frames: {num_frames}")
          else:
            if verbosity>=1: print(f"  WARNING! Movie file (EER or TIFF) for '{curr_xml}' does not exist, continuing...")

        if xml_idx==0:
          first_frames= num_frames
        elif xml_idx==1:
          if num_frames != first_frames:
            print("ERROR!!")
            print(f"  Number of frames in first two movies is different! ({first_frames},{num_frames})")
            print("  Exiting...")
            exit()
        else:
          print(f"Unknown state, xml_idx={xml_idx}, exiting...")
          exit()
      # End first-2 IF-THEN
    # End scan-movie IF-THEN
  # End XML loop

  if options.debug: printvars('num_frames', True)

  # End directory loop
  if verbosity>=1:
    print(f"\nDefocus range: {max_df:.1f} to {min_df:.1f} um")
    print(  f"Tilt range: {min_tilt:.1f} to {max_tilt:.1f} degrees")
    if not options.no_scan: print(f"Number of frames: {num_frames}")

  # Process text
  sw_and_version= f"{sw_text} v {'.'.join(version_text.split('.', 3)[:3])}"
  kv_str= f"{int(float(volt_text)/1000)} keV"
  aperture_text= f"{c1_text}, {c2_text}, {c3_text}"
  df_range= f"{max_df:.1f} to  {min_df:.1f}"
  frames_text= str(num_frames)
  mag_wx= f"{mag_text[:3]} {mag_text[3:]} x"
  pixel_size= f"{float(apix_x_text)*1e10:.3f}"
  if min_tilt != max_tilt:
    tilt_range= f"{min_tilt:.1f} to {max_tilt:.1f}"
  else:
    tilt_range= f"{tilt_degrees:.1f}"
  cam_exp_text= f"{float(cam_exp_text):.2f}"
  #printvars('tilt_range',True)

  # Build RTF
  rtf_content= generate_rtf_table(
      scope_title,
      sw_and_version,
      cam_text,
      count_text,
      kv_str,
      aperture_text,
      obj_aperture,
      df_range,
      spot_text,
      frames_text,
      mag_wx,
      pixel_size,
      movie_format,
      tilt_range,
      slit_text,
      cam_exp_text
    )

  # Write the RTF content to a file
  with open(options.output, "w") as file:
      file.write(rtf_content)

  if verbosity>=1:
    print(f"\nDone! Report written to: {options.output}")

def find_simple_tag(root, search_string, namespace_dict, pad=None, prefix=None):
  """
  Finds a simple XML tag containing a given search string under a branch in an XML tree

  Parameters:
    root : XML element tree
    search_string : string to search for
    namespace_dict : namespace under which to look for search string
    pad : optional text between printed tag & value
    prefix : optional leading text when printing to screen

  Returns:
      value
  """

  dict_key= list( namespace_dict.keys() )[0]
  found_element= root.find(f'.//{dict_key}:{search_string}', namespace_dict)
  namespace_str= "{" + namespace_dict[dict_key] + "}"
  cleaned_tag= found_element.tag.replace(namespace_str, '')
  found_value= found_element.text

  if pad:
    if prefix:
      print(" ", prefix, cleaned_tag, pad, found_value)
    else:
      print(" ", cleaned_tag, pad, found_value)

  ###return cleaned_tag, found_value
  return found_value

def find_complex_tag(root, search_string, namespace_dict, parent_key='KeyValueOfstringanyType', pad=None):
  """
  Finds a complex XML tag which contains a parent key.
  Key is of the form: './/{dict_key}:{parent_key}[a:Key="{search_string}"]/a:Key'

  Parameters:
    root : XML element tree
    search_string : string to search for
    namespace_dict : namespace under which to look for search string
    parent_key : parent key, where key is of the form: './/{dict_key}:{parent_key}[a:Key="{search_string}"]/a:Key'
    pad : optional text between printed tag & value

  Returns:
      value
  """

  dict_key= list( namespace_dict.keys() )[0]
  key_string= f'.//{dict_key}:{parent_key}[a:Key="{search_string}"]/a:Key'
  search_element= root.find(f'.//{dict_key}:{parent_key}[a:Key="{search_string}"]/a:Key', namespace_dict)

  if search_element is not None:
    try:
      found_key= search_element.text
    except AttributeError as e:
      print(f"type: {type(search_element)}")
      printvars(['dict_key','parent_key','search_string'])
      print('\n',e)

    found_value= root.find(f'.//{dict_key}:{parent_key}[a:Key="{search_string}"]/a:Value', namespace_dict).text

    if pad:
      print(" ", found_key, pad, found_value)

    ###return found_key, found_value
    return found_value
  else:
    ###return None, "N/A"
    return "N/A"

def find_element(root, search_string, namespace_dict, prefix="   ", debug=False):
  """
  Finds an element containing a given search string under a branch in an XML tree

  Parameters:
    root : XML element tree
    search_string : string to search for
    namespace_dict : namespace under which to look for search string
    prefix : optional leading text when printing to screen
    debug : boolean for printing to screen

  Functions called:
    loop_branch

  Returns:
      XML element
  """

  dict_key= list( namespace_dict.keys() )[0]
  found_element= root.find(f'.//{dict_key}:{search_string}', namespace_dict)

  if debug:
    print(f"  found_element: {type(found_element)} {found_element}")
    namespace_str= "{" + namespace_dict[dict_key] + "}"
    loop_branch(found_element, namespace_str, prefix=prefix)

  return found_element

def loop_branch(parent, namespace_shared_str, prefix="   "):
  """
  Prints cleaned-up XML tag

  Parameters:
    parent : XML tree
    namespace_shared_str : (string) namespace
    prefix : leading text when printing to screen

  """

  for e_idx, ele in enumerate(parent):
    cleaned_tag= ele.tag.replace(namespace_shared_str, "")
    print(f"  {prefix} {e_idx} {cleaned_tag}")

def check_frames(fn, debug=False):
  """
  Gets the number of frames in a micrograph movie

  Parameters:
    fn : filename
    debug : optional boolean flag to print verbose information

  Functions called:
    check_exe

  Returns:
      number of frames
  """

  path_header= check_exe('header')

  # Read header
  hdr_out = subprocess.run([path_header, fn], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

  # Try to catch subprocess errors
  if hdr_out.returncode!= 0:
      print(f"\nERROR!! IMOD 'header' command failed! \n\t{hdr_out.stderr.decode('utf-8')}\tExiting...\n")
      exit(12)

  # Split into lines
  hdr_lines = hdr_out.stdout.decode('utf-8').split('\n')

  # Find line with 'sections'
  section_lines= [x for x in hdr_lines if 'sections' in x]
  assert len(section_lines) == 1, f"ERROR!! IMOD header output has multiple lines (or none) containing the string 'sections'! \n\t'{section_lines}'"

  # Get last three entries containing dimensions
  movie_dims= [ eval(i) for i in section_lines[0].split()[-3:] ]

  return movie_dims[2]

def check_exe(search_exe, debug=False):
  """
  Looks for executable path
  Adapted from snartomo-heatwave.py

  Parameters:
    search_exe (str) : executable to check
    debug (bool, optional) : flag to write path

  Returns:
    executable path
  """

  # If not found yet, simply try a 'which'
  exe_path = shutil.which(search_exe)

  # If not found, throw an error
  if exe_path is None:
    print(f"\nWARNING! No executable found for command '{search_exe}'")
  else:
    if debug : print(f"  Path to executable '{search_exe}': {exe_path}")

  return exe_path

def generate_rtf_table(
    scope_title,
    sw_and_version,
    cam_text,
    count_text,
    kv_str,
    aperture_text,
    obj_aperture,
    df_range,
    spot_text,
    num_frames,
    mag_wx,
    pixel_size,
    movie_format,
    tilt_range,
    slit_text,
    cam_exp_text
  ):
  """
  Generates RTF table

  Parameters:
    scope_title
    sw_and_version
    cam_text
    count_text
    kv_str
    aperture_text
    obj_aperture
    df_range
    spot_text
    num_frames
    mag_wx
    pixel_size
    movie_format
    tilt_range
    slit_text
    cam_exp_text

  Returns:
    RTF text
  """

  # Repeated data
  empty_cell=r"\cell \alang1081 \sa0\alang1025 \f5"
  cell_format_1=r"\clbrdrt\brdrs\brdrw10\brdrcf1\clbrdrl\brdrs\brdrw10\brdrcf1\clpadt72\clbrdrb\brdrs\brdrw10\brdrcf1\clbrdrr\brdrs\brdrw10\brdrcf1"
  cell_format_2=r"\cell\row\trowd\trleft10\ltrrow\trrh-432" + cell_format_1 + r"\clcbpat18\clvertalc"
  cell_format_6=r"\cell\row\trowd\trleft10\ltrrow" + cell_format_1 + r"\cellx2422" + cell_format_1 + r"\cellx4431"
  cell_format_3=r"}" + cell_format_6 + cell_format_1 + r"\cellx7563" + cell_format_1 + r"\cellx9183 \alang1081 \sa0{\alang1025 \lang2057\lang2057\b\f5" + "\n"
  cell_format_4=r"}\cell \alang1081 \sa0{\alang1025 \f5" + "\n"
  cell_format_5=r"}\cell \alang1081 \sa0{\alang1025 \lang2057\lang2057\b\f5" + "\n"
  cell_format_7=r"}{\alang1025 \lang2057\lang2057\b\f5" + "\n"

  rtf_string = r"{\rtf1\ansi\deff4\adeflang1025" + "\n"
  rtf_string+= r"{\fonttbl{\f0\froman\fprq2\fcharset0 Times New Roman;}{\f1\froman\fprq2\fcharset2 Symbol;}{\f2\fswiss\fprq2\fcharset0 Arial;}{\f3\froman\fprq2\fcharset0 Liberation Serif{\*\falt Times New Roman};}{\f4\fswiss\fprq0\fcharset128 Calibri;}{\f5\fswiss\fprq0\fcharset128 Calibri Light;}{\f6\fnil\fprq2\fcharset0 Calibri;}{\f7\fnil\fprq2\fcharset0 0;}}" + "\n"
  rtf_string+= r"{\colortbl;\red0\green0\blue0;\red0\green0\blue255;\red0\green255\blue255;\red0\green255\blue0;\red255\green0\blue255;\red255\green0\blue0;\red255\green255\blue0;\red255\green255\blue255;\red0\green0\blue128;\red0\green128\blue128;\red0\green128\blue0;\red128\green0\blue128;\red128\green0\blue0;\red128\green128\blue0;\red128\green128\blue128;\red192\green192\blue192;\red203\green211\blue222;\red234\green237\blue241;}" + "\n"
  rtf_string+= r"{\stylesheet{\alang1081 \f4 Normal;}}" + "\n"
  rtf_string+= r"\hyphauto1\viewscale160" + "\n"
  rtf_string+= r"\trowd\ltrrow" + cell_format_1 + r"\clcbpat17\clvertalc\cellx9183 \alang1081 \sa160{\alang1025 \b\f5" + "\n"
  rtf_string+= r"Data acquisition parameters}" + cell_format_2 + r"\cellx4431" + cell_format_1 + r"\clcbpat18\clvertalc\cellx9183 \alang1081 \sa160{\alang1025 \i\b\f5" + "\n"
  rtf_string+= r"Hardware}\cell \alang1081 \sa160{\alang1025 \i\b\f5" + "\n"
  rtf_string+= "Software" + cell_format_3
  rtf_string+= r"Microscope" + cell_format_4
  rtf_string+= scope_title + cell_format_5
  rtf_string+= r"Data collection" + cell_format_4
  rtf_string+= sw_and_version + cell_format_3
  rtf_string+= r"Detector (mode)}\cell \alang1081 \sa0{\alang1025 \lang2057\lang2057\f5" + "\n"
  if count_text == "true" : cam_text+= " (counting)"
  rtf_string+= cam_text + cell_format_5
  rtf_string+= r"Collection method" + cell_format_4
  rtf_string+= r"AFIS}" + cell_format_6 + r"\clbrdrt\brdrs\brdrw10\brdrcf1\clbrdrl\brdrs\brdrw10\brdrcf1\clpadt72\cellx7563\clbrdrt\brdrs\brdrw10\brdrcf1\clpadt72\cellx9183 \alang1081 \sa0{\alang1025 \lang2057\lang2057\b\f5" + "\n"
  rtf_string+= r"Accelerating voltage" + cell_format_4
  rtf_string+= kv_str + r"}\cell \alang1081 \sa0\alang1025 \f5" + "\n"
  rtf_string+= empty_cell + "\n"
  rtf_string+= cell_format_6 + r"\clbrdrl\brdrs\brdrw10\brdrcf1\clpadt72\cellx7563\clpadt72\cellx9183 \alang1081 \sa0{\alang1025 \lang2057\lang2057\b\f5" + "\n"
  rtf_string+= r"Spherical aberration" + cell_format_4
  rtf_string+= r"2.7}\cell \alang1081 \sa0\alang1025 \f5" + "\n"
  rtf_string+= empty_cell + "\n"
  rtf_string+= cell_format_2 + r"\cellx9183 \alang1081 \sa0{\alang1025 \i\b\f5" + "\n"
  rtf_string+= "Data acquisition parameters" + cell_format_3
  rtf_string+= r"Apertures (C1, C2, C3)" + cell_format_4
  rtf_string+= aperture_text + cell_format_5
  rtf_string+= r"Defocus range (\u181\'3fm, step size)" + cell_format_4
  rtf_string+= r"}{\alang1025 \f5" + "\n"
  rtf_string+= df_range + r"}" + cell_format_6 + r"" + cell_format_1 + r"\cellx7563" + cell_format_1 + r"\cellx9183 \alang1081 \sa0{\alang1025 \lang2057\lang2057\b\f5" + "\n"
  rtf_string+= r"Objective aperture" + cell_format_4
  if obj_aperture == "None":
    rtf_string+= r"-" + cell_format_5
  else:
    rtf_string+= obj_aperture + cell_format_5
  rtf_string+= r"Dose (e/px/sec)" + cell_format_4
  rtf_string+= r"DOSE/SEC}" + cell_format_6 + r"" + cell_format_1 + r"\cellx7563" + cell_format_1 + r"\cellx9183 \alang1081 \sa0{\alang1025 \lang2057\lang2057\b\f5" + "\n"
  rtf_string+= r"Energy filter slit (eV)" + cell_format_4
  rtf_string+= slit_text + cell_format_5
  rtf_string+= r"Dose (e/\u197\'3f}{\alang1025 \lang2057\super\lang2057\b\f5" + "\n"
  rtf_string+= r"2" + cell_format_7
  rtf_string+= r"/sec)" + cell_format_4
  rtf_string+= r"DOSE/A2}" + cell_format_6 + r"" + cell_format_1 + r"\cellx7563" + cell_format_1 + r"\cellx9183 \alang1081 \sa0{\alang1025 \lang2057\lang2057\b\f5" + "\n"
  rtf_string+= r"Illuminated area (\u181\'3fm)" + cell_format_4
  rtf_string+= r"ILL_AREA" + cell_format_5
  rtf_string+= r"Exposure time (sec)" + cell_format_4
  rtf_string+= cam_exp_text + cell_format_3
  rtf_string+= r"Spot size" + cell_format_4
  rtf_string+= spot_text + cell_format_5
  rtf_string+= r"Total dose (e/\u197\'3f}{\alang1025 \lang2057\super\lang2057\b\f5" + "\n"
  rtf_string+= r"2}{\alang1025 \lang2057\lang2057\b\f5" + "\n"
  rtf_string+= r")" + cell_format_4
  rtf_string+= r"TOTAL_DOSE" + cell_format_3
  rtf_string+= r"Tilt angle (\uc2 \u176\'81\'8b)\uc1 " + cell_format_4
  rtf_string+= tilt_range + cell_format_5
  rtf_string+= r"Frames (#)" + cell_format_4

  if movie_format=='eer':
    rtf_string+= num_frames + r"}" + cell_format_6 + r"" + cell_format_1 + r"\cellx7563" + cell_format_1 + r"\cellx9183 \alang1081 \sa0{\alang1025 \lang2057\lang2057\b\f5" + "\n"
  else:
    rtf_string+= r"FRAMES}" + cell_format_6 + r"" + cell_format_1 + r"\cellx7563" + cell_format_1 + r"\cellx9183 \alang1081 \sa0{\alang1025 \lang2057\lang2057\b\f5" + "\n"

  rtf_string+= r"Nominal magnification}\cell\pard\plain \rtlch\ltrch\hich\intbl\sa0{\rtlch\alang1025 \ltrch\hich\af5\f5" + "\n"
  rtf_string+= mag_wx + cell_format_5
  rtf_string+= r"Fractions (#)" + cell_format_4
  rtf_string+= num_frames + r"}" + cell_format_6 + cell_format_1 + r"\cellx7563" + cell_format_1 + r"\cellx9183 \alang1081 \sa0{\alang1025 \lang2057\lang2057\b\f5" + "\n"
  rtf_string+= r"Pixel size (\u197\'3f}{\alang1025 \lang2057\super\lang2057\b\f5" + "\n"
  rtf_string+= r"2" + cell_format_7
  rtf_string+= r")" + cell_format_4
  rtf_string+= pixel_size + cell_format_5
  rtf_string+= r"Movie format" + cell_format_4

  if movie_format:
    rtf_string+= movie_format + r"}\cell\row \alang1081" + "\n"
  else:
    rtf_string+= r"MOVIE_FMT}\cell\row \alang1081" + "\n"

  rtf_string+= "\n" + r"\par  \alang1081" + "\n"
  rtf_string+= r"\par }"

  return rtf_string

#def column2_text(string):
  #return r"{\rtlch \ltrch\fs22\kerning0\dbch " + string + r"}\cell\plain \rtlch" + "\n"

#def column4_text(string):
  #return r"{\rtlch \ltrch\fs22\kerning0\dbch " + string + r"}" + "\n"

def parse_command_line():
    """
    Parse the command line.  Adapted from sxmask.py

    Arguments:
        None

    Returns:
        Parsed arguments object
    """

    parser= argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        usage=USAGE,
        epilog=MODIFIED
        )

    parser.add_argument(
        "--directory", "-d",
        type=str,
        default='Images-Disc1',
        help="Top-level images directory")

    parser.add_argument(
        "--output", "-o",
        type=str,
        default='report.rtf',
        help="Output RTF report")

    parser.add_argument(
        "--no_scan", "-n",
        action="store_true",
        help="Flag to skip EER scan")

    parser.add_argument(
        "--progress",
        action="store_true",
        help="Show progress bar")

    parser.add_argument(
        "--verbosity", "-v",
        type=int,
        default=1,
        help=f"Verbosity level [0..{MAX_VERBOSITY}]")
    # Verbosity levels:
    #   1: overall summary, progress bar
    #   2: directory summary
    #   3: list XML
    #   4: print tags

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Debugging flag")

    return parser.parse_args()

if __name__ == "__main__":

    options= parse_command_line()
    ##print(options)
    ##exit()

    main(options)
