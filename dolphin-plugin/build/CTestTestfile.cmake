# CMake generated Testfile for 
# Source directory: /home/lex/Рабочий стол/quickview/dolphin-plugin
# Build directory: /home/lex/Рабочий стол/quickview/dolphin-plugin/build
# 
# This file includes the relevant testing commands required for 
# testing this directory and lists subdirectories to be tested as well.
add_test(appstreamtest "/usr/bin/cmake" "-DAPPSTREAMCLI=/usr/bin/appstreamcli" "-DINSTALL_FILES=/home/lex/Рабочий стол/quickview/dolphin-plugin/build/install_manifest.txt" "-P" "/usr/share/ECM/kde-modules/appstreamtest.cmake")
set_tests_properties(appstreamtest PROPERTIES  _BACKTRACE_TRIPLES "/usr/share/ECM/kde-modules/KDECMakeSettings.cmake;173;add_test;/usr/share/ECM/kde-modules/KDECMakeSettings.cmake;191;appstreamtest;/usr/share/ECM/kde-modules/KDECMakeSettings.cmake;0;;/home/lex/Рабочий стол/quickview/dolphin-plugin/CMakeLists.txt;12;include;/home/lex/Рабочий стол/quickview/dolphin-plugin/CMakeLists.txt;0;")
