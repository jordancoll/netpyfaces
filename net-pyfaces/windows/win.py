from ctypes import *
from ctypes import wintypes
from ctypes.wintypes import WORD
from itertools import ifilter

from winerror import ERROR_BUFFER_OVERFLOW, NO_ERROR, ERROR_NO_DATA

from win_types import AF_UNSPEC, AF_LINK, PIP_ADAPTER_ADDRESSES, PSOCKADDR, WSADATA, PWSADATA, AF_INET, GAA_FLAG_INCLUDE_PREFIX

# Aliases

GetAdaptersAddresses = WINFUNCTYPE(c_ulong, c_ulong, c_ulong, c_void_p, PIP_ADAPTER_ADDRESSES, c_void_p)(('GetAdaptersAddresses', windll.iphlpapi))
WSAAddressToString = WINFUNCTYPE(c_int, PSOCKADDR, wintypes.DWORD, c_void_p, c_wchar_p, c_void_p)(('WSAAddressToStringW', windll.ws2_32))
WSAStartup = WINFUNCTYPE(c_int, WORD, PWSADATA)(('WSAStartup', windll.ws2_32))
WSACleanup = WINFUNCTYPE(c_int)(('WSACleanup', windll.ws2_32))


def _iterate_from(list_item):
    while list_item:
        yield list_item
        list_item = list_item.contents.Next


def _get_adapters_addresses(flags):
    buflen = c_ulong(0)
    adapter_addresses = None
    
    ret = ERROR_BUFFER_OVERFLOW
    attempts = 5
    
    while ret == ERROR_BUFFER_OVERFLOW and attempts:
        adapter_addresses = cast((buflen.value * c_byte)(), PIP_ADAPTER_ADDRESSES)
        
        ret = GetAdaptersAddresses(AF_UNSPEC, flags, None, adapter_addresses, byref(buflen))
        attempts -= 1
    
    if ret != NO_ERROR and ret != ERROR_NO_DATA:
        raise OSError("Unable to obtain adapter information.")
    
    return adapter_addresses


def _address_to_string(psockaddr, addrlen):
    buflen = wintypes.DWORD(256)
    buf = None
    
    ret = 1
    attempts = 5
    
    while ret and attempts:
        buf = create_unicode_buffer(buflen.value)
        ret = WSAAddressToString(psockaddr, addrlen, None, buf, byref(buflen))
        attempts -= 1
    
    return buf.value if not ret else None


class WindowsInterfaces(object):
    def __init__(self):
        self.adapter_addresses = None
    
    def __enter__(self):
        data = WSADATA()
        WSAStartup(514, byref(data))
        self.adapter_addresses = _get_adapters_addresses(GAA_FLAG_INCLUDE_PREFIX)
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        WSACleanup()
    
    def interfaces(self):
        result = []
        
        for adapter in _iterate_from(self.adapter_addresses):
            result.append(adapter.contents.AdapterName)
        
        return result
    
    def ifaddresses(self, ifname):
        result = {}
        adapter = next(ifilter(lambda a: a.contents.AdapterName == ifname, _iterate_from(self.adapter_addresses)), None)
        
        if adapter is None:  # interface not found
            raise ValueError("You must specify a valid interface name.")
        
        physical_addr = ':'.join(
                "{0:02x}".format(adapter.contents.PhysicalAddress[i])
                for i in range(0, adapter.contents.PhysicalAddressLength)
        )
        
        result[AF_LINK] = [{'addr': physical_addr}]
        
        for unicast_addr in _iterate_from(adapter.contents.FirstUnicastAddress):
            family = unicast_addr.contents.Address.lpSockaddr.contents.sa_family
            address = _address_to_string(unicast_addr.contents.Address.lpSockaddr, unicast_addr.contents.Address.iSockaddrLength)
            
            if not address:
                continue
            
            if family == AF_INET:
                pass
        
        return result


if __name__ == '__main__':
    with WindowsInterfaces() as ifs:
        # print ifs.interfaces()
        print ifs.ifaddresses(u'{CC06281E-16BE-4CA7-9756-4A073D3C1D5D}')
