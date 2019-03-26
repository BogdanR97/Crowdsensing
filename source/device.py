"""
This module represents a device.

Computer Systems Architecture Course
Assignment 1
March 2019
"""

from threading import Thread, Lock, RLock
from Queue import PriorityQueue
from barriers import SimpleBarrier, ReusableBarrier


class Device(object):
    """
    Class that represents a device.
    """

    def __init__(self, device_id, sensor_data, supervisor):
        """
        Constructor.

        @type device_id: Integer
        @param device_id: the unique id of this node; between 0 and N-1

        @type sensor_data: List of (Integer, Float)
        @param sensor_data: a list containing (location, data) as measured by this device

        @type supervisor: Supervisor
        @param supervisor: the testing infrastructure's control and validation component
        """
        self.device_id = device_id
        self.sensor_data = sensor_data
        self.supervisor = supervisor
        self.threads_no = 8
        self.scripts = PriorityQueue()  # Current timepoint scripts + End-of-Timepoint scripts
        self.future_scripts = PriorityQueue()   # Scripts already executed in the current timepoint
        self.neighbours = []
        self.neighbours_lock = Lock()   # Structures which ensure that only one thread
        self.no_neighbours = True       # will get the neighbours per device
        self.timepoint_barr = None      # Guarantees synchronization between threads
                                        # at the end of a timepoint

        self.timepoint_lock = Lock()    # Structures which ensure that only one thread
        self.next_timepoint = False     # will reset properties of a device for the next timepoint
        self.location_locks = {}    # Guarantees that only one thread will have access
                                    # to all data of a certain location
        self.setup_barr = None      # Guarantees synchronization of threads
                                    # once the devices are set up
        self.threads = []
        for _ in xrange(self.threads_no):
            self.threads.append(DeviceThread(self))

    def __str__(self):
        """
        Pretty prints this device.

        @rtype: String
        @return: a string containing the id of this device
        """
        return "Device %d" % self.device_id

    def setup_devices(self, devices):
        """
        Setup the devices before simulation begins.
        Assures device communication - devices will share the same instances of objets
        location_locks, timepoint_barr and setup_barr.

        @type devices: List of Device
        @param devices: list containing all devices
        """

        if self.device_id != 0:
            return

        devices_no = len(devices)
        timepoint_barr = ReusableBarrier(self.threads_no * devices_no)
        setup_barr = SimpleBarrier(self.threads_no * devices_no)
        location_locks = {}

        for device in devices:
            for location in device.sensor_data:
                location_locks[location] = RLock()

        for device in devices:
            device.timepoint_barr = timepoint_barr
            device.setup_barr = setup_barr
            device.location_locks = location_locks

            for i in xrange(self.threads_no):
                device.threads[i].start()


    def assign_script(self, script, location):
        """
        Provide a script for the device to execute.
        Regular scripts have to be executed first in a timepoint, even though the device
        has received an End-of-Timepoint script. Thus, the priority of regular scripts
        is 0 and End-of-Timepoint scripts have 1.
        An End-of-Timepoint script is sent per device. This method sends one End-of-Timepoint
        script per thread.

        @type script: Script
        @param script: the script to execute from now on at each timepoint; None if the
            current timepoint has ended

        @type location: Integer
        @param location: the location for which the script is interested in
        """

        if script is not None:
            self.scripts.put((0, script, location))
        else:
            for _ in xrange(self.threads_no):
                self.scripts.put((1, None, None))

    def get_data(self, location):
        """
        Returns the pollution value this device has for the given location.
        The thread which calls this method will acquire the lock for the
        given location (or will wait for it to be released), so that
        no other thread from any device will be able to concurently access
        this data.

        @type location: Integer
        @param location: a location for which obtain the data

        @rtype: Float
        @return: the pollution value
        """
        if location in self.sensor_data:
            self.location_locks[location].acquire()
            return self.sensor_data[location]
        return None

    def set_data(self, location, data):
        """
        Sets the pollution value stored by this device for the given location.
        This method is called by a thread once the processing of data for a certain
        location is done. The thread will have to release the lock it has, allowing
        other waiting threads to acquire it.

        @type location: Integer
        @param location: a location for which to set the data

        @type data: Float
        @param data: the pollution value
        """
        if location in self.sensor_data:
            self.sensor_data[location] = data
            self.location_locks[location].release()

    def get_neighbours(self):
        """
        Allows only one thread per device to get the neighbours of a device
        at a certain timepoint.
        """
        with self.neighbours_lock:
            if self.no_neighbours:
                self.next_timepoint = True
                self.no_neighbours = False
                self.neighbours = self.supervisor.get_neighbours()

    def advance_timepoint(self):
        """
        Allows only one thread per devive to reset properties of a device
        at the end of a timepoint.
        """
        with self.timepoint_lock:
            if self.next_timepoint:
                self.no_neighbours = True
                self.next_timepoint = False

                # Put proccessed scripts back in the queue for future runs
                for q_elem in self.future_scripts.queue:
                    self.scripts.put(q_elem)
                self.future_scripts = PriorityQueue()

    def shutdown(self):
        """
        Instructs the device to shutdown (terminate all threads). This method
        is invoked by the tester. This method must block until all the threads
        started by this device terminate.
        """
        for i in xrange(self.threads_no):
            self.threads[i].join()


class DeviceThread(Thread):
    """
    Class that implements the device's worker thread.
    """

    def __init__(self, device):
        """
        Constructor.

        @type device: Device
        @param device: the device which owns this thread
        """
        Thread.__init__(self, name="Device Thread %d" % device.device_id)
        self.device = device

    def run(self):
        self.device.setup_barr.wait()

        # Runs untill the session is over. Gets the neighbours of a device
        # at the start of every timepoint.
        while True:

            self.device.get_neighbours()

            if self.device.neighbours is None:
                break

            # Gets scripts and run them until an End-of-Timepoint script is received
            while True:

                (pq_number, script, location) = self.device.scripts.get()

                # End-of-Timepoint script has been received - exit the loop
                if pq_number == 1:
                    self.device.timepoint_barr.wait()
                    self.device.advance_timepoint()
                    self.device.timepoint_barr.wait()
                    break

                # Gets the data of neighbours for the given location
                script_data = []
                for device in self.device.neighbours:
                    data = device.get_data(location)
                    if data is not None:
                        script_data.append(data)

                # Gets device's data for the given location
                data = self.device.get_data(location)
                if data is not None:
                    script_data.append(data)

                # Runs the script on the received data
                if script_data != []:
                    result = script.run(script_data)

                    # Update data of neighbours
                    for device in self.device.neighbours:
                        device.set_data(location, result)
                    # Update data of the device
                    self.device.set_data(location, result)
                # Save the processed script for future runs
                self.device.future_scripts.put((pq_number, script, location))
