import types

import torch

# Create our python implementation dict so that the C++ module
# can access it during its initialization and also register aten impls.
from ._aten_impl import impl_factory as impl_factory  # noqa: F401
from ._device_daemon import driver


# Load the C++ Module
import torch_remote._C  # isort:skip # type: ignore[import] # noqa: F401


def _create_module():
    module = types.ModuleType("_RemoteMod")

    class device:
        r"""Context-manager that changes the selected device.

        Args:
            device (torch.device or int): device index to select. It's a no-op if
                this argument is a negative integer or ``None``.
        """

        def __init__(self, device):
            self.idx = torch.accelerator._get_device_index(device, optional=True)
            self.prev_idx = -1

        def __enter__(self):
            self.prev_idx = driver.exec("exchangeDevice", self.idx)

        def __exit__(self, type, value, traceback):
            self.idx = driver.exec("uncheckedSetDevice", self.prev_idx)
            return False

    def device_count() -> int:
        return driver.exec("deviceCount")

    def is_available():
        return True

    def current_device():
        return torch.accelerator.current_device_index()

    def get_rng_state(device="remote"):
        if isinstance(device, str):
            device = torch.device(device)
        elif isinstance(device, int):
            device = torch.device("remote", device)
        idx = device.index
        if idx is None:
            idx = current_device()
        default_generator = torch_remote._C._get_default_generator(idx)
        return default_generator.get_state()

    def set_rng_state(new_state, device="remote"):
        if isinstance(device, str):
            device = torch.device(device)
        elif isinstance(device, int):
            device = torch.device("remote", device)
        idx = device.index
        if idx is None:
            idx = current_device()
        default_generator = torch_remote._C._get_default_generator(idx)
        default_generator.set_state(new_state)

    def initial_seed() -> int:
        _lazy_init()
        idx = current_device()
        default_generator = torch_remote._C._get_default_generator(idx)
        return default_generator.initial_seed()

    def manual_seed(seed: int) -> None:
        seed = int(seed)

        idx = current_device()
        default_generator = torch_remote._C._get_default_generator(idx)
        default_generator.manual_seed(seed)

    def manual_seed_all(seed: int) -> None:
        seed = int(seed)

        for idx in range(device_count()):
            default_generator = torch_remote._C._get_default_generator(idx)
            default_generator.manual_seed(seed)

    def is_initialized():
        return module._initialized

    def _is_in_bad_fork():
        return False

    def _lazy_init():
        if is_initialized():
            return
        torch_remote._C._init()
        module._initialized = True

    module.is_available = is_available  # type: ignore[assignment]

    module._initialized = False  # type: ignore[assignment]
    module._lazy_init = _lazy_init  # type: ignore[assignment]
    module.is_initialized = is_initialized  # type: ignore[assignment]

    module.device = device  # type: ignore[assignment]
    module.device_count = device_count  # type: ignore[assignment]
    module.current_device = current_device  # type: ignore[assignment]
    module.get_rng_state = get_rng_state  # type: ignore[assignment]
    module.set_rng_state = set_rng_state  # type: ignore[assignment]
    module._is_in_bad_fork = _is_in_bad_fork  # type: ignore[assignment]
    module.initial_seed = initial_seed  # type: ignore[assignment]
    module.manual_seed = manual_seed  # type: ignore[assignment]
    module.manual_seed_all = manual_seed_all  # type: ignore[assignment]
    

    return module


# Set all the appropriate state on PyTorch
torch.utils.rename_privateuse1_backend("remote")
torch._register_device_module("remote", _create_module())
torch.utils.generate_methods_for_privateuse1_backend(for_storage=True)

# Patch tensor methods and factory functions to support BackendDevice
from .utils import _add_tensor_methods, _patch_torch_factory_functions
_add_tensor_methods()
_patch_torch_factory_functions()

# Import device management
from .device import create_modal_device, BackendDevice, GPUType, get_device_registry