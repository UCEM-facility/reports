#!/usr/bin/env python

import xml.etree.ElementTree as ET
import argparse
import os
import shutil
import subprocess
import glob
import inspect
import tqdm

USAGE="""
Navigates directory tree and extracts selected information from EPU XML file series.

USAGE:
  %s <epu_project_directory> <options>

""" % ((__file__,)*1)

MODIFIED="Modified 2025 Jan 13"
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
      if not options.no_scan: print("Scanning first 2 movies for number of frames...")
      print()

  # Initialize
  min_df=+999.9
  max_df=-999.9
  num_frames= None
  movie_format= None

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

    # DetectorCommercialName
    cam_key, cam_tag= find_complex_tag(root, "DetectorCommercialName", namespace_array_dict, parent_key='KeyValueOfstringanyType', pad='\t\t' if verbosity>=4 else '')

    # Voltage
    volt_tag, volt_text= find_simple_tag(root, "AccelerationVoltage", namespace_shared_dict, pad='\t\t\t' if verbosity>=4 else '')

    # Software version
    sw_tag, sw_text= find_simple_tag(root, "ApplicationSoftware", namespace_shared_dict, pad='\t\t\t' if verbosity>=4 else '')
    version_tag, version_text= find_simple_tag(root, "ApplicationSoftwareVersion", namespace_shared_dict, pad='\t\t' if verbosity>=4 else '')

    # Apertures
    c1_key, c1_text= find_complex_tag(root, "Aperture[C1].Name", namespace_array_dict, parent_key='KeyValueOfstringanyType', pad='\t\t\t' if verbosity>=4 else '')
    c2_key, c2_text= find_complex_tag(root, "Aperture[C2].Name", namespace_array_dict, parent_key='KeyValueOfstringanyType', pad='\t\t\t' if verbosity>=4 else '')
    c3_key, c3_text= find_complex_tag(root, "Aperture[C3].Name", namespace_array_dict, parent_key='KeyValueOfstringanyType', pad='\t\t\t' if verbosity>=4 else '')

    # optics -> SpotIndex
    spot_tag, spot_text= find_simple_tag(root, "SpotIndex", namespace_shared_dict, pad='\t\t\t\t' if verbosity>=4 else '')

    # TemMagnification -> NominalMagnification
    mag_tag, mag_text= find_simple_tag(root, "NominalMagnification", namespace_shared_dict, pad='\t\t\t' if verbosity>=4 else '')

    # SpatialScale -> pixelSize -> {x,y} -> numericValue
    apix_element= find_element(root, "pixelSize", namespace_shared_dict, prefix='  ')
    apix_x_element= find_element(apix_element, "x", namespace_shared_dict)
    apix_x_tag, apix_x_text= find_simple_tag(apix_x_element, "numericValue", namespace_shared_dict, pad='\t\t\t' if verbosity>=4 else '', prefix='x')
    apix_y_element= find_element(apix_element, "y", namespace_shared_dict)
    apix_y_tag, apix_y_text= find_simple_tag(apix_y_element, "numericValue", namespace_shared_dict, pad='\t\t\t' if verbosity>=4 else '', prefix='y')
    assert apix_x_text==apix_y_text, f"UH OH!! Pixel size in x ({apix_x_text}) doesn't equal in y ({apix_y_text})!"

    # AppliedDefocus
    df_key, df_text= find_complex_tag(root, "AppliedDefocus", namespace_array_dict, parent_key='KeyValueOfstringanyType', pad='\t\t\t' if verbosity>=4 else '')

    # Check against defocus extrema
    df_microns= float(df_text)*1e+6
    if -min_df < -df_microns : min_df=df_microns
    if -max_df > -df_microns : max_df=df_microns

    # Detectors[EF-Falcon].TotalDose (UNITS?)
    f4_dose_key, f4_dose_text= find_complex_tag(root, "Detectors[EF-Falcon].TotalDose", namespace_array_dict, parent_key='KeyValueOfstringanyType', pad='\t' if verbosity>=4 else '')

    # Dose (UNITS?)
    custom_dose_key, custom_dose_text= find_complex_tag(root, "Dose", namespace_array_dict, parent_key='KeyValueOfstringanyType', pad='\t\t\t\t\t' if verbosity>=4 else '')

    # Detectors[EF-Falcon].ExposureTime
    custom_element= find_element(root, "CustomData", namespace_shared_dict)
    f4_exp_key, f4_exp_text= find_complex_tag(custom_element, "Detectors[EF-Falcon].ExposureTime", namespace_array_dict, parent_key='KeyValueOfstringanyType', pad='\t' if verbosity>=4 else '')

    # microscopeData -> acquisition -> camera -> ExposureTime
    camera_element= find_element(root, "camera", namespace_shared_dict)
    cam_exp_key, cam_exp_text= find_simple_tag(camera_element, "ExposureTime", namespace_shared_dict, pad='\t\t\t\t' if verbosity>=4 else '')

    # Detectors[EF-Falcon].FrameRate
    frames_key, frames_text= find_complex_tag(root, "Detectors[EF-Falcon].FrameRate", namespace_array_dict, parent_key='KeyValueOfstringanyType', pad='\t' if verbosity>=4 else '')

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
    if not options.no_scan: print(f"Number of frames: {num_frames}")

  # Process text
  sw_and_version= f"{sw_text} v {'.'.join(version_text.split('.', 3)[:3])}"
  kv_str= f"{int(float(volt_text)/1000)} keV"
  aperture_text= f"{c1_text}, {c2_text}, {c3_text}"
  df_range= f"{max_df:.1f} to {min_df:.1f}"
  frames_text= str(num_frames)
  mag_wx= f"{mag_text[:3]} {mag_text[3:]} x"
  pixel_size= f"{float(apix_x_text)*1e10:.3f}"

  # Build RTF
  rtf_content= generate_rtf_table(sw_and_version,cam_tag,kv_str,aperture_text,df_range,spot_text,frames_text,mag_wx,pixel_size, movie_format)

  # Write the RTF content to a file
  with open(options.output, "w") as file:
      file.write(rtf_content)

  if verbosity>=1:
    print(f"\nDone! Wrote report to {options.output}")

def loop_branch(parent, namespace_shared_str, prefix="   "):
  for e_idx, ele in enumerate(parent):
    cleaned_tag= ele.tag.replace(namespace_shared_str, "")
    print(f"  {prefix} {e_idx} {cleaned_tag}")

def find_simple_tag(root, search_string, namespace_dict, pad=None, prefix=None):
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

  return cleaned_tag, found_value

def find_complex_tag(root, search_string, namespace_dict, parent_key='KeyValueOfstringanyType', pad=None):
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

    return found_key, found_value
  else:
    return None, "N/A"

def find_element(root, search_string, namespace_dict, prefix="   ", debug=False):
  dict_key= list( namespace_dict.keys() )[0]
  found_element= root.find(f'.//{dict_key}:{search_string}', namespace_dict)

  if debug:
    print(f"  found_element: {type(found_element)} {found_element}")
    namespace_str= "{" + namespace_dict[dict_key] + "}"
    loop_branch(found_element, namespace_str, prefix=prefix)

  return found_element

def check_frames(fn, debug=False):
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

def generate_rtf_table(sw_and_version,cam_tag,kv_str,aperture_text,df_range,spot_text,num_frames,mag_wx,pixel_size, movie_format):
  # Repeated data (that I understand)
  row_format=r"\cell\row\trowd\trleft5\clpadt108\clcbpat18\cellx2976\clbrdrt\brdrs\brdrw10\brdrcf19\clbrdrl\brdrs\brdrw10\brdrcf19\clpadt108\clcbpat18\cellx4535\clbrdrt\brdrs\brdrw10\brdrcf19\clbrdrl\brdrs\brdrw10\brdrcf19\clpadt108\clcbpat18\cellx7655\clbrdrt\brdrs\brdrw10\brdrcf19\clbrdrl\brdrs\brdrw10\brdrcf19\clpadt108\clcbpat18\cellx9356\plain \rtlch"
  empty_cell=r"\cell\plain \rtlch \rtlch \ltrch\fs22\kerning0\dbch"

  rtf_string = r"{\rtf1\ansi\deff4\adeflang1025" + "\n"
  rtf_string+= r"{\fonttbl{\f4\fswiss\fprq0\fcharset128 Calibri;}{\f5\fswiss\fprq0\fcharset128 Calibri Light;}{\f6\fnil\fprq2\fcharset0 Calibri;}}" + "\n"
  rtf_string+= r"{\colortbl;\red0\green0\blue0;\red0\green0\blue255;\red0\green255\blue255;\red0\green255\blue0;\red255\green0\blue255;\red255\green0\blue0;\red255\green255\blue0;\red255\green255\blue255;\red0\green0\blue128;\red0\green128\blue128;\red0\green128\blue0;\red128\green0\blue128;\red128\green0\blue0;\red128\green128\blue0;\red128\green128\blue128;\red192\green192\blue192;\red47\green84\blue150;\red242\green242\blue242;\red191\green191\blue191;}" + "\n"
  rtf_string+= r"{\stylesheet{\snext0\rtlch \ltrch\lang1033\langfe2052\hich\af4\loch\widctlpar\hyphpar0\ltrpar\cf0\f4\fs24\lang1033\kerning1\dbch\af7\langfe2052 Normal;}}" + "\n"
  rtf_string+= r"\deftab709\hyphauto1\viewscale100" + "\n"
  rtf_string+= r"\paperh16838\paperw11906\margl1134\margr1134\margt1134\margb1134" + "\n"
  rtf_string+= r"{\*\ftnsep\chftnsep}\pgndec\plain \rtlch \ltrch\lang1033\langfe2052\hich\af4\loch\widctlpar\hyphpar0\ltrpar\cf0\f4\fs24\lang1033\kerning1\dbch\af7\langfe2052\ql\ltrpar\loch" + "\n"
  rtf_string+= r"\par\trleft5\clbrdrt\brdrs\brdrw10\brdrcf19\clbrdrl\brdrs\brdrw10\brdrcf19\clpadt108\cellx2976\clbrdrt\brdrs\brdrw10\brdrcf19\cellx9356" + "\n"
  rtf_string+= r"\cf17\f5\dbch\sb240" + "\n"
  rtf_string+= r"{\b\kerning0 Data acquisition parameters}" + "\n"
  rtf_string+= r"\par \rtlch \sb0\ab \loch\fs22 \cell\plain" + "\n"
  rtf_string+= r"\cell\row\trowd\trleft5\clbrdrt\brdrs\brdrw10\brdrcf19\clpadt108\clpadr108\clcbpat18\cellx2976\clbrdrt\brdrs\brdrw10\brdrcf19\clcbpat18\cellx4535\clbrdrt\brdrs\brdrw10\brdrcf19\clpadt108\clcbpat18\cellx7655\clbrdrt\brdrs\brdrw10\brdrcf19\clcbpat18\cellx9356" + "\n"
  rtf_string+= r"{\fs22\i\b Hardware}" + "\n"
  rtf_string+= r"\cell \ltrch\fs22 \cell" + "\n"
  rtf_string+= r"{\fs22\i\b Software}" + "\n"
  rtf_string+= r"\cell \rtlch \cell" + "\n"
  rtf_string+= r"\row\trowd\trleft5\clpadt108\cellx2976\clpadt108\cellx4535\clpadt108\cellx7655\clbrdrt\brdrs\brdrw10\brdrcf19\clpadt108\cellx9356\plain" + "\n"
  rtf_string+= r"{\fs22\b Microscope}\cell\plain" + "\n"
  rtf_string+= column2_text("Titan Krios")
  rtf_string+= bold_text("Data collection")
  rtf_string+= column4_text(sw_and_version)
  rtf_string+= row_format + "\n"
  rtf_string+= bold_text("Detector (mode)")
  rtf_string+= column2_text("Falcon4i")
  rtf_string+= bold_text("Collection method")
  rtf_string+= column4_text("AFIS")
  rtf_string+= r"\cell\row\trowd\trleft5\clpadt108\cellx2976\clbrdrt\brdrs\brdrw10\brdrcf19\clbrdrl\brdrs\brdrw10\brdrcf19\clpadt108\cellx4535\clbrdrt\brdrs\brdrw10\brdrcf19\clbrdrl\brdrs\brdrw10\brdrcf19\clpadt108\cellx7655\clbrdrt\brdrs\brdrw10\brdrcf19\clbrdrl\brdrs\brdrw10\brdrcf19\clpadt108\cellx9356\plain \rtlch" + "\n"
  rtf_string+= bold_text("Accelerating voltage")
  rtf_string+= column2_text(kv_str)
  rtf_string+= bold_text("Movie format")
  rtf_string+= column4_text(movie_format)
  rtf_string+= row_format + "\n"
  rtf_string+= bold_text("Spherical aberration")
  rtf_string+= column2_text("2.7")
  rtf_string+= r"\rtlch \ltrch\fs22\kerning0\dbch" + "\n"
  rtf_string+= empty_cell + "\n"
  rtf_string+= r"\cell\row\trowd\trleft5\clpadt108\cellx2976\clbrdrt\brdrs\brdrw10\brdrcf19\clbrdrl\brdrs\brdrw10\brdrcf19\clpadt108\cellx4535\clbrdrt\brdrs\brdrw10\brdrcf19\clbrdrl\brdrs\brdrw10\brdrcf19\clpadt108\cellx7655\clbrdrt\brdrs\brdrw10\brdrcf19\clbrdrl\brdrs\brdrw10\brdrcf19\clpadt108\cellx9356\plain \rtlch \rtlch\ab \ltrch\fs22\b\kerning0\dbch" + "\n"
  rtf_string+= empty_cell + "\n"
  rtf_string+= empty_cell + "\n"
  rtf_string+= empty_cell + "\n"
  rtf_string+= row_format + "\n"
  rtf_string+= r"{\rtlch\ai\ab \ltrch\fs22\i\b\kerning0\dbch Data acquisition parameters}\cell\plain \rtlch" + "\n"
  rtf_string+= r"\rtlch \ltrch\fs22\kerning0\dbch" + "\n"
  rtf_string+= empty_cell + "\n"
  rtf_string+= empty_cell + "\n"
  rtf_string+= r"\cell\row\trowd\trleft5\clpadt108\cellx2976\clbrdrt\brdrs\brdrw10\brdrcf19\clbrdrl\brdrs\brdrw10\brdrcf19\clpadt108\cellx4535\clbrdrt\brdrs\brdrw10\brdrcf19\clbrdrl\brdrs\brdrw10\brdrcf19\clpadt108\cellx7655\clbrdrt\brdrs\brdrw10\brdrcf19\clbrdrl\brdrs\brdrw10\brdrcf19\clpadt108\cellx9356\plain \rtlch" + "\n"
  rtf_string+= bold_text("Apertures (C1, C2, C3)")
  rtf_string+= column2_text(aperture_text)
  rtf_string+= bold_text(r"Defocus range (}{\rtlch\ab \ltrch\fs22\b\kerning0\dbch \u181\'3f}{\rtlch\ab \ltrch\fs22\b\kerning0\dbch m)")
  rtf_string+= column4_text(df_range)
  rtf_string+= row_format + "\n"
  rtf_string+= bold_text("Objective aperture")
  rtf_string+= column2_text("-")
  rtf_string+= bold_text("Dose (e/px/sec)")
  rtf_string+= column4_text("9.09")
  rtf_string+= r"\cell\row\trowd\trleft5\clpadt108\cellx2976\clbrdrt\brdrs\brdrw10\brdrcf19\clbrdrl\brdrs\brdrw10\brdrcf19\clpadt108\cellx4535\clbrdrt\brdrs\brdrw10\brdrcf19\clbrdrl\brdrs\brdrw10\brdrcf19\clpadt108\cellx7655\clbrdrt\brdrs\brdrw10\brdrcf19\clbrdrl\brdrs\brdrw10\brdrcf19\clpadt108\cellx9356\plain \rtlch" + "\n"
  rtf_string+= bold_text("Energy filter slit (eV)")
  rtf_string+= column2_text("10")
  rtf_string+= bold_text(r"Dose (e/\u197\'3f}{\rtlch\ab \ltrch\super\fs22\b\kerning0\dbch 2}{\rtlch\ab \ltrch\fs22\b\kerning0\dbch /sec)")
  rtf_string+= column4_text("18.33")
  rtf_string+= row_format + "\n"
  rtf_string+= bold_text(r"Illuminated area (}{\rtlch\ab \ltrch\fs22\b\kerning0\dbch \u181\'3f}{\rtlch\ab \ltrch\fs22\b\kerning0\dbch m)")
  rtf_string+= column2_text("0.70")
  rtf_string+= bold_text("Exposure time (sec)")
  rtf_string+= column4_text("2.72")
  rtf_string+= r"\cell\row\trowd\trleft5\clpadt108\cellx2976\clbrdrt\brdrs\brdrw10\brdrcf19\clbrdrl\brdrs\brdrw10\brdrcf19\clpadt108\cellx4535\clbrdrt\brdrs\brdrw10\brdrcf19\clbrdrl\brdrs\brdrw10\brdrcf19\clpadt108\cellx7655\clbrdrt\brdrs\brdrw10\brdrcf19\clbrdrl\brdrs\brdrw10\brdrcf19\clpadt108\cellx9356\plain \rtlch" + "\n"
  rtf_string+= bold_text("Spot size")
  rtf_string+= column2_text("5")
  rtf_string+= bold_text(r"Total dose (e/\u197\'3f}{\rtlch\ab \ltrch\super\fs22\b\kerning0\dbch 2}{\rtlch\ab \ltrch\fs22\b\kerning0\dbch )")
  rtf_string+= column4_text("50")
  rtf_string+= row_format + "\n"
  rtf_string+= bold_text(r"Tilt angle (}{\rtlch\ab \ltrch\fs22\b\kerning0\dbch \uc2 \u176\'81\'8b)\uc1 ")
  rtf_string+= column2_text("0")
  rtf_string+= bold_text("Total frames (#)")
  rtf_string+= column4_text(num_frames)
  rtf_string+= r"\cell\row\trowd\trleft5\clpadt108\cellx2976\clbrdrt\brdrs\brdrw10\brdrcf19\clbrdrl\brdrs\brdrw10\brdrcf19\clpadt108\cellx4535\clbrdrt\brdrs\brdrw10\brdrcf19\clbrdrl\brdrs\brdrw10\brdrcf19\clpadt108\cellx7655\clbrdrt\brdrs\brdrw10\brdrcf19\clbrdrl\brdrs\brdrw10\brdrcf19\clpadt108\cellx9356\plain \rtlch" + "\n"
  rtf_string+= bold_text("Nominal magnification")
  rtf_string+= column2_text(mag_wx)
  rtf_string+= r"\rtlch\ab \ltrch\fs22\b\kerning0\dbch" + "\n"
  rtf_string+= empty_cell + "\n"
  rtf_string+= row_format + "\n"
  rtf_string+= bold_text(r"Pixel size (\u197\'3f}{\rtlch\ab \ltrch\fs22\b\kerning0\dbch)")
  rtf_string+= column2_text(pixel_size)
  rtf_string+= r"\rtlch \ltrch\fs22\kerning0\dbch" + "\n"
  rtf_string+= empty_cell + "\n"
  rtf_string+= r"\cell\row\trowd\trleft5\clpadt108\cellx2976\clbrdrt\brdrs\brdrw10\brdrcf19\clbrdrl\brdrs\brdrw10\brdrcf19\clpadt108\cellx4535\clbrdrt\brdrs\brdrw10\brdrcf19\clbrdrl\brdrs\brdrw10\brdrcf19\clpadt108\cellx7655\clbrdrt\brdrs\brdrw10\brdrcf19\clbrdrl\brdrs\brdrw10\brdrcf19\clpadt108\cellx9356\plain \rtlch \rtlch\ab \ltrch\fs22\b\kerning0\dbch" + "\n"
  rtf_string+= empty_cell + "\n"
  rtf_string+= empty_cell + "\n"
  rtf_string+= empty_cell + "\n"
  rtf_string+= r"\cell\row\plain \rtlch \ltrch\lang1033\langfe2052\hich\af4\loch\widctlpar\hyphpar0\ltrpar\cf0\f4\fs24\lang1033\kerning1\dbch\af7\langfe2052\ql\ltrpar\loch" + "\n"
  rtf_string+= r"\par }" + "\n"

  return rtf_string

def column2_text(string):
  return r"{\rtlch \ltrch\fs22\kerning0\dbch " + string + r"}\cell\plain \rtlch" + "\n"

def column4_text(string):
  return r"{\rtlch \ltrch\fs22\kerning0\dbch " + string + r"}" + "\n"

def bold_text(string):
  return r"{\rtlch\ab \ltrch\fs22\b\kerning0\dbch " + string + r"}\cell\plain \rtlch" + "\n"

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
