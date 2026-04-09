cmake_minimum_required(VERSION 3.16)
project(quickview-dolphin-plugin)

set(CMAKE_CXX_STANDARD 17)
set(QT_MIN_VERSION "6.4.0")
set(KF_MIN_VERSION "6.0.0")

find_package(ECM ${KF_MIN_VERSION} REQUIRED NO_MODULE)
set(CMAKE_MODULE_PATH ${ECM_MODULE_PATH})

include(KDEInstallDirs)
include(KDECMakeSettings)
include(KDECompilerSettings NO_POLICY_SCOPE)
include(ECMDeprecationSettings)

find_package(Qt6 ${QT_MIN_VERSION} REQUIRED COMPONENTS Core Gui Widgets)
find_package(KF6 ${KF_MIN_VERSION} REQUIRED COMPONENTS CoreAddons KIO)

kcoreaddons_add_plugin(quickviewplugin
    SOURCES quickviewplugin.cpp
    INSTALL_NAMESPACE "kf6/kfileitemaction"
)

target_link_libraries(quickviewplugin
    KF6::KIOWidgets
    KF6::CoreAddons
    Qt6::Widgets
)
